from __future__ import annotations

from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .agents.mock_customer_data_resolver import MockCustomerDataResolver
from .agents.logic_verification import verify_issue_logic
from .agents.rag_query import build_rag_query
from .agents.report_composer import DECISION_LABELS, compose_issue_report
from .agents.decision_gate import apply_decision_gate, assess_risk
from .agents.question_builder import expected_interest_question
from .agents.router import _load_dotenv, build_case_request
from .agents.facts import missing_facts, resolve_facts
from .finance.mock_data import MockBankClient
from .agents.logic_graph import build_logic_graph
from .mcp.finance.client import FinanceMCPClient
from .rag.retrieval import SearchIndex
from .schemas import (
    AuditEvent,
    CaseAnalysis,
    CaseAnalyzeRequest,
    Decision,
    IssueAnalysis,
    IssueInput,
    ReviewRequest,
    ReviewResponse,
    ReviewQueueItem,
)
from .supabase_store import SupabaseStore


ROOT = Path(__file__).resolve().parents[1]
_load_dotenv()
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
CHUNKS_PATH = DATA_DIR / "corpus" / "all.jsonl"
FALLBACK_CHUNKS_PATH = ROOT / "server" / "rag" / "chunks.jsonl"
DICTIONARY_PATH = DATA_DIR / "dictionary" / "fine_financial_glossary.json"
_INDEX: SearchIndex | None = None
_DICTIONARY: list[dict[str, object]] | None = None
MOCK_BANK_CLIENT = MockBankClient()
FINANCE_MCP_CLIENT = FinanceMCPClient()
CUSTOMER_DATA_RESOLVER = MockCustomerDataResolver(FINANCE_MCP_CLIENT)
SUPABASE_STORE = SupabaseStore()


def get_index() -> SearchIndex:
    global _INDEX
    if _INDEX is None:
        index_path = CHUNKS_PATH if CHUNKS_PATH.exists() else FALLBACK_CHUNKS_PATH
        _INDEX = SearchIndex.from_data_dir(DATA_DIR, chunks_path=index_path)
    return _INDEX


def get_dictionary() -> list[dict[str, object]]:
    global _DICTIONARY
    if _DICTIONARY is None:
        try:
            _DICTIONARY = json.loads(DICTIONARY_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            _DICTIONARY = []
    return _DICTIONARY


def _admin_corpus(chunk: object) -> str:
    doc_type = str(getattr(chunk, "doc_type", ""))
    path = str(getattr(chunk, "path", "")).split(":", 1)[-1].replace("\\", "/")
    if doc_type == "glossary" or path.startswith("dictionary/"):
        return "glossary"
    if doc_type == "case" or path.startswith("cases/"):
        return "cases"
    if doc_type == "law" or path.startswith(("regulations/", "공통규정/")):
        return "regulations"
    if path.startswith("products/"):
        return "products"
    return "other"


def _admin_date_status(effective_from: date | None, effective_to: date | None) -> str:
    today = date.today()
    if effective_from and effective_from > today:
        return "scheduled"
    if effective_to and effective_to < today:
        return "expired"
    if effective_from:
        return "current"
    return "unknown"


def _admin_document_rows() -> list[dict[str, object]]:
    grouped: dict[str, list[object]] = defaultdict(list)
    for chunk in get_index().chunks:
        grouped[chunk.doc_id].append(chunk)

    rows: list[dict[str, object]] = []
    for doc_id, chunks in grouped.items():
        first = chunks[0]
        effective_from = first.effective_from
        effective_to = first.effective_to
        embedded = sum(1 for chunk in chunks if chunk.embedding)
        rows.append(
            {
                "doc_id": doc_id,
                "path": first.path,
                "doc_type": first.doc_type,
                "corpus": _admin_corpus(first),
                "products": sorted({product for chunk in chunks for product in chunk.product}),
                "source": first.source,
                "published_at": first.published_at,
                "effective_from": effective_from,
                "effective_to": effective_to,
                "effective_status": _admin_date_status(effective_from, effective_to),
                "chunk_count": len(chunks),
                "page_count": len({chunk.page for chunk in chunks}),
                "embedding_count": embedded,
                "index_status": "ready",
            }
        )
    return sorted(rows, key=lambda row: (str(row["corpus"]), str(row["path"])))


def _admin_case_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for case in CASE_STORE.values():
        case_events = [event for event in AUDIT_LOG if event.case_id == case.case_id]
        created_at = min((event.created_at for event in case_events), default=None)
        for issue in case.issues:
            rows.append(
                {
                    "case_id": case.case_id,
                    "created_at": created_at,
                    "prompt": case.prompt,
                    "issue_id": issue.issue_id,
                    "product": issue.product,
                    "issue_type": issue.issue_type,
                    "control": issue.decision.control,
                    "risk_level": issue.risk_level,
                    "human_review_required": issue.human_review_required,
                    "evidence_count": len(issue.evidence_refs),
                    "generated_by": issue.report.generated_by,
                }
            )
    return sorted(rows, key=lambda row: str(row["created_at"] or ""), reverse=True)


@app.get("/api/v1/admin/overview")
def get_admin_overview() -> dict[str, object]:
    documents = _admin_document_rows()
    cases = _admin_case_rows()
    controls = Counter(str(row["control"]) for row in cases)
    effective = Counter(str(row["effective_status"]) for row in documents)
    manifest_path = DATA_DIR / "corpus" / "manifest.json"
    manifest: dict[str, object] = {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    return {
        "documents": {
            "total": len(documents),
            "chunks": sum(int(row["chunk_count"]) for row in documents),
            "current": effective["current"],
            "expired": effective["expired"],
            "unknown": effective["unknown"],
            "scheduled": effective["scheduled"],
        },
        "cases": {
            "total": len({str(row["case_id"]) for row in cases}),
            "issues": len(cases),
            "controls": dict(controls),
            "human_review": sum(1 for row in cases if row["human_review_required"]),
            "no_evidence": sum(1 for row in cases if row["evidence_count"] == 0),
            "fallback": sum(1 for row in cases if row["generated_by"] == "fallback"),
        },
        "corpus": manifest,
        "telemetry": {
            "available": False,
            "message": "실행 단계별 처리시간·토큰·비용 수집은 아직 연결되지 않았습니다.",
        },
    }


@app.get("/api/v1/admin/documents")
def get_admin_documents(
    q: str = "",
    corpus: str = "",
    product: str = "",
    status: str = "",
) -> list[dict[str, object]]:
    needle = q.strip().lower()
    rows = _admin_document_rows()
    if needle:
        rows = [
            row for row in rows
            if needle in str(row["path"]).lower()
            or needle in str(row["doc_id"]).lower()
            or needle in str(row["doc_type"]).lower()
        ]
    if corpus:
        rows = [row for row in rows if row["corpus"] == corpus]
    if product:
        rows = [row for row in rows if product in row["products"]]
    if status:
        rows = [row for row in rows if row["effective_status"] == status]
    return rows


@app.get("/api/v1/admin/documents/{doc_id}")
def get_admin_document(doc_id: str, limit: int = 100) -> dict[str, object]:
    chunks = [chunk for chunk in get_index().chunks if chunk.doc_id == doc_id]
    if not chunks:
        raise HTTPException(status_code=404, detail="document not found")
    limit = min(max(limit, 1), 300)
    first = chunks[0]
    return {
        "doc_id": doc_id,
        "path": first.path,
        "doc_type": first.doc_type,
        "corpus": _admin_corpus(first),
        "products": sorted({product for chunk in chunks for product in chunk.product}),
        "source": first.source,
        "published_at": first.published_at,
        "effective_from": first.effective_from,
        "effective_to": first.effective_to,
        "effective_status": _admin_date_status(first.effective_from, first.effective_to),
        "chunk_count": len(chunks),
        "chunks": [
            {
                "chunk_id": chunk.chunk_id,
                "page": chunk.page,
                "section": chunk.section,
                "effective_from": chunk.effective_from,
                "effective_to": chunk.effective_to,
                "text": chunk.text,
            }
            for chunk in chunks[:limit]
        ],
    }


@app.get("/api/v1/admin/search")
def admin_search(
    q: str = "",
    product: str = "",
    as_of: date | None = None,
    top_k: int = 10,
) -> dict[str, object]:
    query = q.strip()
    top_k = min(max(top_k, 1), 30)
    if not query:
        return {"query": "", "as_of": as_of or date.today(), "results": []}
    results = get_index().search(
        query,
        product=product or None,
        as_of=as_of or date.today(),
        top_k=top_k,
    )
    return {
        "query": query,
        "product": product or None,
        "as_of": as_of or date.today(),
        "index_source": get_index().source,
        "results": [result.model_dump(mode="json") for result in results],
    }


@app.get("/api/v1/admin/cases")
def get_admin_cases(
    control: str = "",
    product: str = "",
    review_only: bool = False,
) -> list[dict[str, object]]:
    rows = _admin_case_rows()
    if control:
        rows = [row for row in rows if row["control"] == control]
    if product:
        rows = [row for row in rows if row["product"] == product]
    if review_only:
        rows = [row for row in rows if row["human_review_required"]]
    return rows


@app.get("/api/v1/admin/cases/{case_id}")
def get_admin_case(case_id: str) -> dict[str, object]:
    case = CASE_STORE.get(case_id)
    if case is None:
        case = SUPABASE_STORE.get_case(case_id)
        if case is not None:
            CASE_STORE[case_id] = case
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")
    return {
        "case": case.model_dump(mode="json"),
        "audit": [event.model_dump(mode="json") for event in AUDIT_LOG if event.case_id == case_id],
        "reviews": [review.model_dump(mode="json") for review in REVIEW_STORE.get(case_id, [])],
    }


@app.get("/api/v1/admin/audit")
def get_admin_audit(limit: int = 100) -> list[dict[str, object]]:
    limit = min(max(limit, 1), 500)
    return [event.model_dump(mode="json") for event in AUDIT_LOG[-limit:]][::-1]


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
    evidence = get_index().search_many(
        rag_query.variants or [rag_query.text],
        product=issue.product,
        as_of=request.as_of or date.today(),
    )

    risk_flags: list[str] = []
    if missing:
        risk_flags.append("missing_facts")
    if resolution.conflicts:
        risk_flags.append("fact_conflict")
    if not evidence:
        risk_flags.append("evidence_insufficient")
    if (customer_data is None or customer_data.get("access_granted") is False) and issue.product in {"예금", "적금", "대출"}:
        risk_flags.append("customer_data_unavailable")

    control = "ask" if missing or resolution.conflicts or not evidence else "proceed"
    risk_level, risk_reasons = assess_risk(
        issue_type=issue.issue_type,
        target=issue.target,
        routing_confidence=issue.routing_confidence,
        risk_flags=risk_flags,
    )
    if "안내 금액" in missing:
        next_steps = [expected_interest_question(facts)]
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
        routing_confidence=issue.routing_confidence,
        routing_method=issue.routing_method,
        focal=focal,
        target=issue.target,
        mock_data=mock_view,
        facts=facts,
        missing_facts=list(dict.fromkeys(missing)),
        fact_resolution=resolution,
        retrieval_query=rag_query.text,
        evidence_refs=evidence,
        decision=Decision(control=control, risk_flags=risk_flags),
        risk_level=risk_level,
        risk_reasons=risk_reasons,
        content_scope={"mode": "summary", "requires_user_confirmation": False},
        next_steps=next_steps,
    )
    result = result.model_copy(update={"logic_verification": verify_issue_logic(result, use_llm=use_llm_logic)})
    gate = apply_decision_gate(result)
    result = result.model_copy(
        update={
            "decision": Decision(control=gate.control, risk_flags=result.decision.risk_flags),
            "human_review_required": gate.human_review,
            "risk_level": "critical" if gate.control == "hold" else result.risk_level,
        }
    )
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
    event = AuditEvent(
        event_id=f"audit_{uuid4().hex[:12]}",
        case_id=case_id,
        event_type=event_type,
        actor=actor,
        created_at=datetime.now(timezone.utc),
        payload=payload,
    )
    AUDIT_LOG.append(event)
    SUPABASE_STORE.save_audit(event)


def _audit_issues(result: CaseAnalysis) -> list[dict[str, object]]:
    return [
        {
            "issue_id": issue.issue_id,
            "control": issue.decision.control,
            "risk_flags": issue.decision.risk_flags,
            "risk_level": issue.risk_level,
            "risk_reasons": issue.risk_reasons,
            "routing_confidence": issue.routing_confidence,
            "routing_method": issue.routing_method,
            "human_review_required": issue.human_review_required,
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
    get_index()  # 워커 스레드 경쟁 전에 인덱스를 1회만 빌드
    use_llm = None if not request.issues else False
    with ThreadPoolExecutor(max_workers=min(len(issues), 4)) as pool:
        analyzed = list(
            pool.map(
                lambda issue: _analyze_issue(
                    issue,
                    request,
                    customer_data,
                    use_llm_report=use_llm,
                    use_llm_rag=use_llm,
                    use_llm_logic=use_llm,
                ),
                issues,
            )
        )
    result = CaseAnalysis(
        case_id=case_id,
        session_id=request.session_id,
        prompt=request.prompt,
        issues=analyzed,
    )
    result = result.model_copy(update={"logic_graph": build_logic_graph(result)})
    CASE_STORE[case_id] = result
    SUPABASE_STORE.save_case(result)
    _record_audit(case_id, "case.analyzed", "system", {"issues": _audit_issues(result)})
    return result


@app.get("/api/v1/cases/{case_id}", response_model=CaseAnalysis)
def get_case(case_id: str) -> CaseAnalysis:
    result = CASE_STORE.get(case_id)
    if result is None:
        result = SUPABASE_STORE.get_case(case_id)
        if result is not None:
            CASE_STORE[case_id] = result
    if result is None:
        raise HTTPException(status_code=404, detail="case not found")
    return result


@app.get("/api/v1/reviews/queue", response_model=list[ReviewQueueItem])
def get_review_queue() -> list[ReviewQueueItem]:
    return [
        ReviewQueueItem(
            case_id=case.case_id,
            issue_id=issue.issue_id,
            product=issue.product,
            issue_type=issue.issue_type,
            control=issue.decision.control,
            risk_level=issue.risk_level,
            risk_reasons=issue.risk_reasons,
            routing_confidence=issue.routing_confidence,
            routing_method=issue.routing_method,
        )
        for case in CASE_STORE.values()
        for issue in case.issues
        if issue.human_review_required or issue.decision.control == "hold"
    ]

@app.post("/api/v1/cases/{case_id}/review", response_model=ReviewResponse)
def review_case(case_id: str, review: ReviewRequest) -> ReviewResponse:
    current = CASE_STORE.get(case_id)
    if current is None:
        current = SUPABASE_STORE.get_case(case_id)
        if current is not None:
            CASE_STORE[case_id] = current
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
            updates["human_review_required"] = decision.control == "hold"
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
    SUPABASE_STORE.save_case(updated)
    response = ReviewResponse(
        review_id=f"review_{uuid4().hex[:12]}",
        case_id=case_id,
        applied=True,
        reviewer_id=review.reviewer_id,
        note=review.note,
        analysis=updated,
    )
    REVIEW_STORE.setdefault(case_id, []).append(response)
    SUPABASE_STORE.save_review(response)
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
        case = SUPABASE_STORE.get_case(case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="case not found")
        CASE_STORE[case_id] = case
    events = [event for event in AUDIT_LOG if event.case_id == case_id]
    return events or SUPABASE_STORE.list_audits(case_id)
