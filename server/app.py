from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException

from .facts import missing_facts, resolve_facts
from .logic_graph import build_logic_graph
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
CASE_STORE: dict[str, CaseAnalysis] = {}
REVIEW_STORE: dict[str, list[ReviewResponse]] = {}
AUDIT_LOG: list[AuditEvent] = []
CHUNKS_PATH = ROOT / 'server' / 'chunks.jsonl'
_INDEX: SearchIndex | None = None


def get_index() -> SearchIndex:
    global _INDEX
    if _INDEX is None:
        _INDEX = SearchIndex.from_data_dir(DATA_DIR, chunks_path=CHUNKS_PATH)
    return _INDEX


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


def _analyze_issue(issue: IssueInput, request: CaseAnalyzeRequest) -> IssueAnalysis:
    resolution = resolve_facts(issue.facts)
    missing = missing_facts(issue.required_facts, resolution)
    query = f"{issue.product} {issue.issue_type} {issue.text}"
    evidence = get_index().search(query, product=issue.product, as_of=request.as_of or date.today())

    risk_flags: list[str] = []
    if missing:
        risk_flags.append("missing_facts")
    if resolution.conflicts:
        risk_flags.append("fact_conflict")
    if not evidence:
        risk_flags.append("evidence_insufficient")

    # ponytail: lexical baseline; B's agent layer can replace this with the final policy gate.
    control = "ask" if missing or resolution.conflicts or not evidence else "proceed"
    next_steps = ["근거 문서와 계약·거래 사실을 함께 확인하세요."] if evidence else ["관련 계약서·상품설명서 또는 금융회사 답변을 추가하세요."]
    return IssueAnalysis(
        issue_id=issue.issue_id,
        product=issue.product,
        issue_type=issue.issue_type,
        focal=issue.focal,
        target=issue.target,
        facts=issue.facts,
        missing_facts=missing,
        fact_resolution=resolution,
        evidence_refs=evidence,
        decision=Decision(control=control, risk_flags=risk_flags),
        content_scope={"mode": "summary", "requires_user_confirmation": False},
        next_steps=next_steps,
    )


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
    issues = request.issues or [_fallback_issue(request)]
    result = CaseAnalysis(
        case_id=case_id,
        session_id=request.session_id,
        prompt=request.prompt,
        issues=[_analyze_issue(issue, request) for issue in issues],
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
        updated_issues.append(issue.model_copy(update=updates))

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
