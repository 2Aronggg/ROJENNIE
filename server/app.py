from __future__ import annotations

from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .agent.mock_customer_data_resolver import MockCustomerDataResolver
from .agent.logic_verification import verify_issue_logic
from .agent.rag_query import build_rag_query
from .agent.report_composer import DECISION_LABELS, compose_issue_report
from .agent.decision_gate import apply_decision_gate
from .agent.router import build_case_request
from .facts import missing_facts, resolve_facts
from .mock_data import MockBankClient
from .logic_graph import build_logic_graph
from .mcp_client import FinanceMCPClient
from .retrieval import SearchIndex
from .schemas import (
    AuditEvent,
    CaseAnalysis,
    CaseAnalyzeRequest,
    Decision,
    IssueAnalysis,
    IssueInput,
    ReviewRequest,
    ReviewResponse,
)


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
app = FastAPI(title="Financial Consumer Protection Agent API", version="0.1.0")
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
CASE_STORE: dict[str, CaseAnalysis] = {}
REVIEW_STORE: dict[str, list[ReviewResponse]] = {}
AUDIT_LOG: list[AuditEvent] = []
CHUNKS_PATH = ROOT / 'server' / 'chunks.jsonl'
DICTIONARY_PATH = DATA_DIR / "dictionary" / "fine_financial_glossary.json"
_INDEX: SearchIndex | None = None
_DICTIONARY: list[dict[str, object]] | None = None
MOCK_BANK_CLIENT = MockBankClient()
FINANCE_MCP_CLIENT = FinanceMCPClient()
CUSTOMER_DATA_RESOLVER = MockCustomerDataResolver(FINANCE_MCP_CLIENT)


def get_index() -> SearchIndex:
    global _INDEX
    if _INDEX is None:
        _INDEX = SearchIndex.from_data_dir(DATA_DIR, chunks_path=CHUNKS_PATH)
    return _INDEX


def get_dictionary() -> list[dict[str, object]]:
    global _DICTIONARY
    if _DICTIONARY is None:
        try:
            _DICTIONARY = json.loads(DICTIONARY_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            _DICTIONARY = []
    return _DICTIONARY


@app.get("/dictionary/search")
def search_dictionary(q: str = "", limit: int = 5) -> list[dict[str, object]]:
    needle = q.strip().lower()
    limit = min(max(limit, 1), 20)
    items = get_dictionary()
    if not needle:
        return items[:limit]
    return [
        item for item in items
        if needle in str(item.get("term", "")).lower()
        or needle in str(item.get("definition", "")).lower()
    ][:limit]


def _require_mock_customer(customer_id: str) -> None:
    if MOCK_BANK_CLIENT.get_customer(customer_id) is None:
        raise HTTPException(status_code=404, detail="mock customer not found")


@app.get("/mock/customers/{customer_id}/products")
def get_mock_products(customer_id: str) -> dict[str, list[dict[str, object]]]:
    _require_mock_customer(customer_id)
    return MOCK_BANK_CLIENT.get_products(customer_id)


@app.get("/mock/customers/{customer_id}/deposits")
def get_mock_deposits(customer_id: str) -> list[dict[str, object]]:
    _require_mock_customer(customer_id)
    return MOCK_BANK_CLIENT.get_deposits(customer_id)


@app.get("/mock/customers/{customer_id}/savings")
def get_mock_savings(customer_id: str) -> list[dict[str, object]]:
    _require_mock_customer(customer_id)
    return MOCK_BANK_CLIENT.get_savings(customer_id)


@app.get("/mock/customers/{customer_id}/loans")
def get_mock_loans(customer_id: str) -> list[dict[str, object]]:
    _require_mock_customer(customer_id)
    return MOCK_BANK_CLIENT.get_loans(customer_id)


@app.get("/mock/accounts/{account_id}/transactions")
def get_mock_transactions(account_id: str) -> list[dict[str, object]]:
    if MOCK_BANK_CLIENT.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="mock account not found")
    return MOCK_BANK_CLIENT.get_transactions(account_id)


@app.get("/mock/accounts/{account_id}/repayments")
def get_mock_repayments(account_id: str) -> list[dict[str, object]]:
    if MOCK_BANK_CLIENT.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="mock account not found")
    return MOCK_BANK_CLIENT.get_repayments(account_id)


@app.get("/mock/accounts/{account_id}/rate-history")
def get_mock_rate_history(account_id: str) -> list[dict[str, object]]:
    if MOCK_BANK_CLIENT.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="mock account not found")
    return MOCK_BANK_CLIENT.get_rate_history(account_id)


@app.get("/mock/accounts/{account_id}/notice-history")
def get_mock_notice_history(account_id: str) -> list[dict[str, object]]:
    if MOCK_BANK_CLIENT.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="mock account not found")
    return MOCK_BANK_CLIENT.get_notice_history(account_id)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _fallback_issue(request: CaseAnalyzeRequest) -> IssueInput:
    return IssueInput(
        issue_id="issue_001",
        product="미분류",
        issue_type="미분류",
        text=request.prompt,
    )


def _analyze_issue(
    issue: IssueInput,
    request: CaseAnalyzeRequest,
    customer_data: dict[str, object] | None,
    use_llm_report: bool | None = None,
    use_llm_rag: bool | None = None,
    use_llm_logic: bool | None = None,
) -> IssueAnalysis:
    mock_facts = CUSTOMER_DATA_RESOLVER.facts_for_issue(issue, customer_data)
    facts = [*issue.facts, *mock_facts]
    resolution = resolve_facts(facts)
    missing = missing_facts(issue.required_facts, resolution)
    mock_view = _mock_issue_view(issue, customer_data)
    if issue.product in {"예금", "적금", "대출"}:
        if customer_data is None or customer_data.get("access_granted") is False:
            missing.append("고객 인증·동의 데이터")
        elif not mock_view.get("account"):
            missing.append("가상 계약 데이터")

    rag_query = build_rag_query(issue, use_llm=use_llm_rag)
    evidence = get_index().search(rag_query.text, product=issue.product, as_of=request.as_of or date.today())

    risk_flags: list[str] = []
    if missing:
        risk_flags.append("missing_facts")
    if resolution.conflicts:
        risk_flags.append("fact_conflict")
    if not evidence:
        risk_flags.append("evidence_insufficient")
    if (customer_data is None or customer_data.get("access_granted") is False) and issue.product in {"예금", "적금", "대출"}:
        risk_flags.append("customer_data_unavailable")

    # ponytail: lexical baseline; B's agent layer can replace this with the final policy gate.
    control = "ask" if missing or resolution.conflicts or not evidence else "proceed"
    if "안내 금액" in missing:
        next_steps = ["예상하신 이자 금액은 얼마인가요?"]
    elif evidence:
        next_steps = ["근거 문서와 가상 계약·거래 사실을 함께 확인하세요."]
    else:
        next_steps = ["관련 계약서·상품설명서 또는 금융회사 답변을 추가하세요."]
    focal = {
        **issue.focal,
        "mock_customer_id": request.customer_id,
        "mock_data_available": bool(mock_view.get("account")),
    }
    result = IssueAnalysis(
        issue_id=issue.issue_id,
        product=issue.product,
        issue_type=issue.issue_type,
        focal=focal,
        target=issue.target,
        mock_data=mock_view,
        facts=facts,
        missing_facts=list(dict.fromkeys(missing)),
        fact_resolution=resolution,
        retrieval_query=rag_query.text,
        evidence_refs=evidence,
        decision=Decision(control=control, risk_flags=risk_flags),
        content_scope={"mode": "summary", "requires_user_confirmation": False},
        next_steps=next_steps,
    )
    result = result.model_copy(update={"logic_verification": verify_issue_logic(result, use_llm=use_llm_logic)})
    gate = apply_decision_gate(result)
    result = result.model_copy(update={"decision": Decision(control=gate.control, risk_flags=result.decision.risk_flags)})
    return result.model_copy(update={"report": compose_issue_report(result, use_llm=use_llm_report)})


def _mock_issue_view(issue: IssueInput, customer_data: dict[str, object] | None) -> dict[str, object]:
    if not customer_data:
        return {"available": False, "access_granted": False, "customer_id": None, "account": None, "source_apis": []}
    accounts = customer_data.get("accounts", [])
    product_type = {"예금": "deposit", "적금": "installment_savings", "대출": "loan"}.get(issue.product)
    account = next(
        (item for item in accounts if isinstance(item, dict) and item.get("product_type") == product_type),
        None,
    )
    customer = customer_data.get("customer", {})
    return {
        "available": bool(account),
        "access_granted": customer_data.get("access_granted", False),
        "customer_id": customer.get("customer_id") if isinstance(customer, dict) else None,
        "account": account,
        "source_apis": customer_data.get("source_apis", []),
    }

def _record_audit(case_id: str, event_type: str, actor: str, payload: dict) -> None:
    AUDIT_LOG.append(
        AuditEvent(
            event_id=f"audit_{uuid4().hex[:12]}",
            case_id=case_id,
            event_type=event_type,
            actor=actor,
            created_at=datetime.now(timezone.utc),
            payload=payload,
        )
    )


def _audit_issues(result: CaseAnalysis) -> list[dict[str, object]]:
    return [
        {
            "issue_id": issue.issue_id,
            "control": issue.decision.control,
            "risk_flags": issue.decision.risk_flags,
            "evidence_refs": [ref.chunk_id for ref in issue.evidence_refs],
        }
        for issue in result.issues
    ]

@app.post("/api/v1/cases/analyze", response_model=CaseAnalysis)
def analyze_case(request: CaseAnalyzeRequest) -> CaseAnalysis:
    case_id = request.case_id or f"case_{uuid4().hex[:12]}"
    if request.issues:
        issues = request.issues
    else:
        routed_request = build_case_request(
            request.prompt,
            case_id=case_id,
            session_id=request.session_id,
            customer_id=request.customer_id,
            as_of=request.as_of,
        )
        issues = routed_request.issues or [_fallback_issue(request)]
    customer_data = CUSTOMER_DATA_RESOLVER.resolve(request.customer_id)
    result = CaseAnalysis(
        case_id=case_id,
        session_id=request.session_id,
        prompt=request.prompt,
        issues=[
            _analyze_issue(
                issue,
                request,
                customer_data,
                use_llm_report=None if not request.issues else False,
                use_llm_rag=None if not request.issues else False,
                use_llm_logic=None if not request.issues else False,
            )
            for issue in issues
        ],
    )
    result = result.model_copy(
        update={
            "logic_graph": build_logic_graph(result),
            "regulation_notices": get_index().date_notices(request.as_of or date.today()),
        }
    )
    CASE_STORE[case_id] = result
    _record_audit(case_id, "case.analyzed", "system", {"issues": _audit_issues(result)})
    return result


@app.get("/api/v1/cases/{case_id}", response_model=CaseAnalysis)
def get_case(case_id: str) -> CaseAnalysis:
    result = CASE_STORE.get(case_id)
    if result is None:
        raise HTTPException(status_code=404, detail="case not found")
    return result

@app.post("/api/v1/cases/{case_id}/review", response_model=ReviewResponse)
def review_case(case_id: str, review: ReviewRequest) -> ReviewResponse:
    current = CASE_STORE.get(case_id)
    if current is None:
        raise HTTPException(status_code=404, detail="case not found")

    issue_ids = {issue.issue_id for issue in current.issues}
    unknown_ids = set(review.issue_decisions) | set(review.fact_updates)
    unknown_ids -= issue_ids
    if unknown_ids:
        raise HTTPException(status_code=422, detail={"unknown_issue_ids": sorted(unknown_ids)})

    updated_issues: list[IssueAnalysis] = []
    for issue in current.issues:
        updates: dict[str, object] = {}
        decision = review.issue_decisions.get(issue.issue_id)
        if decision is None and review.control is not None:
            decision = Decision(control=review.control, risk_flags=issue.decision.risk_flags)
        if decision is not None:
            updates["decision"] = decision
        if issue.issue_id in review.fact_updates:
            facts = review.fact_updates[issue.issue_id]
            resolution = resolve_facts(facts)
            updates["facts"] = facts
            updates["fact_resolution"] = resolution
            updates["missing_facts"] = [
                field for field in issue.missing_facts if field not in resolution.latest
            ]
        updated_issue = issue.model_copy(update=updates)
        if decision is not None:
            updated_issue = updated_issue.model_copy(
                update={
                    "report": updated_issue.report.model_copy(
                        update={"current_decision": DECISION_LABELS.get(decision.control, decision.control)}
                    )
                }
            )
        updated_issues.append(updated_issue)

    updated = current.model_copy(update={"issues": updated_issues})
    updated = updated.model_copy(update={"logic_graph": build_logic_graph(updated)})
    CASE_STORE[case_id] = updated
    response = ReviewResponse(
        review_id=f"review_{uuid4().hex[:12]}",
        case_id=case_id,
        applied=True,
        reviewer_id=review.reviewer_id,
        note=review.note,
        analysis=updated,
    )
    REVIEW_STORE.setdefault(case_id, []).append(response)
    _record_audit(
        case_id,
        "human_review.applied",
        review.reviewer_id,
        {
            "review_id": response.review_id,
            "controls": {
                issue_id: decision.control
                for issue_id, decision in review.issue_decisions.items()
            },
            "global_control": review.control,
            "fact_fields": {
                issue_id: [fact.field for fact in facts]
                for issue_id, facts in review.fact_updates.items()
            },
            "note_length": len(review.note),
        },
    )
    return response


@app.get("/api/v1/cases/{case_id}/audit", response_model=list[AuditEvent])
def get_case_audit(case_id: str) -> list[AuditEvent]:
    if case_id not in CASE_STORE:
        raise HTTPException(status_code=404, detail="case not found")
    return [event for event in AUDIT_LOG if event.case_id == case_id]
