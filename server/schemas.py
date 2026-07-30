from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


Control = Literal["proceed", "amend", "ask", "hold"]


class Fact(BaseModel):
    field: str
    value: Any
    source_ref: str | None = None
    event_date: date | None = None
    recorded_date: date | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    conflicts_with: list[str] = Field(default_factory=list)


class EvidenceRef(BaseModel):
    doc_id: str
    chunk_id: str
    path: str
    page: int
    section: str | None = None
    score: float
    snippet: str
    effective_from: date | None = None
    match_type: Literal["full_text", "vector", "hybrid"] = "full_text"


class DocumentChunk(BaseModel):
    doc_id: str
    chunk_id: str
    path: str
    doc_type: str
    product: list[str] = Field(default_factory=list)
    issue_types: list[str] = Field(default_factory=list)
    source: str
    published_at: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    page: int
    section: str | None = None
    text: str
    embedding: list[float] | None = None


class IssueInput(BaseModel):
    issue_id: str
    product: str
    issue_type: str
    text: str = Field(min_length=1)
    focal: dict[str, Any] = Field(default_factory=dict)
    target: dict[str, Any] = Field(default_factory=dict)
    mock_data: dict[str, Any] = Field(default_factory=dict)
    facts: list[Fact] = Field(default_factory=list)
    required_facts: list[str] = Field(default_factory=list)


class CaseAnalyzeRequest(BaseModel):
    case_id: str | None = None
    session_id: str | None = None
    customer_id: str | None = "CUST-001"
    prompt: str = Field(min_length=1)
    as_of: date | None = None
    issues: list[IssueInput] = Field(default_factory=list)


class FactResolution(BaseModel):
    latest: dict[str, Fact] = Field(default_factory=dict)
    conflicts: dict[str, list[str]] = Field(default_factory=dict)


class Decision(BaseModel):
    control: Control
    risk_flags: list[str] = Field(default_factory=list)


class IssueReport(BaseModel):
    complaint_content: str = ""
    issue: str = ""
    processing_result: str = ""
    consumer_cautions: list[str] = Field(default_factory=list)
    used_evidence_chunk_ids: list[str] = Field(default_factory=list)
    current_decision: str = "추가 확인 필요"
    reasoning: str = ""
    follow_up_actions: list[str] = Field(default_factory=list)
    generated_by: Literal["llm", "fallback"] = "fallback"


class LogicVerification(BaseModel):
    summary: str = ""
    checks: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    generated_by: Literal["llm", "fallback"] = "fallback"


class IssueAnalysis(BaseModel):
    issue_id: str
    product: str
    issue_type: str
    focal: dict[str, Any] = Field(default_factory=dict)
    target: dict[str, Any] = Field(default_factory=dict)
    mock_data: dict[str, Any] = Field(default_factory=dict)
    facts: list[Fact] = Field(default_factory=list)
    missing_facts: list[str] = Field(default_factory=list)
    fact_resolution: FactResolution
    retrieval_query: str = ""
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    decision: Decision
    logic_verification: LogicVerification = Field(default_factory=LogicVerification)
    report: IssueReport = Field(default_factory=IssueReport)
    content_scope: dict[str, Any] = Field(default_factory=dict)
    next_steps: list[str] = Field(default_factory=list)


class LogicNode(BaseModel):
    node_id: str
    node_type: str
    label: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class LogicEdge(BaseModel):
    source: str
    target: str
    relation: str


class LogicGraph(BaseModel):
    nodes: list[LogicNode] = Field(default_factory=list)
    edges: list[LogicEdge] = Field(default_factory=list)

class CaseAnalysis(BaseModel):
    case_id: str
    session_id: str | None = None
    prompt: str
    issues: list[IssueAnalysis]
    logic_graph: LogicGraph = Field(default_factory=LogicGraph)
    regulation_notices: list[str] = Field(default_factory=list)

class ReviewRequest(BaseModel):
    reviewer_id: str = "human"
    control: Control | None = None
    issue_decisions: dict[str, Decision] = Field(default_factory=dict)
    fact_updates: dict[str, list[Fact]] = Field(default_factory=dict)
    note: str = Field(default="", max_length=2000)


class ReviewResponse(BaseModel):
    review_id: str
    case_id: str
    applied: bool
    reviewer_id: str
    note: str = ""
    analysis: CaseAnalysis


class AuditEvent(BaseModel):
    event_id: str
    case_id: str
    event_type: str
    actor: str
    created_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)
