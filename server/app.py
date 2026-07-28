from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException

from .facts import missing_facts, resolve_facts
from .retrieval import SearchIndex
from .schemas import CaseAnalysis, CaseAnalyzeRequest, Decision, IssueAnalysis, IssueInput


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
app = FastAPI(title="Financial Consumer Protection Agent API", version="0.1.0")
CASE_STORE: dict[str, CaseAnalysis] = {}
_INDEX: SearchIndex | None = None


def get_index() -> SearchIndex:
    global _INDEX
    if _INDEX is None:
        _INDEX = SearchIndex.from_data_dir(DATA_DIR)
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
    evidence = get_index().search(query, product=issue.product, as_of=request.as_of)

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
    CASE_STORE[case_id] = result
    return result


@app.get("/api/v1/cases/{case_id}", response_model=CaseAnalysis)
def get_case(case_id: str) -> CaseAnalysis:
    result = CASE_STORE.get(case_id)
    if result is None:
        raise HTTPException(status_code=404, detail="case not found")
    return result
