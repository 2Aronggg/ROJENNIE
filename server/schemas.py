from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


Control = Literal["proceed", "amend", "ask", "hold"]
RoutingMethod = Literal["llm", "rules", "manual"]
RiskLevel = Literal["low", "medium", "high", "critical"]
FactSourceType = Literal[
    "USER_STATED",
    "SYSTEM_INFERRED",
    "DOCUMENT_EVIDENCE",
    "PRECEDENT_REFERENCE",
]
InferenceType = Literal["direct_match", "analogical", "unverified"]
EvidenceRole = Literal[
    "direct_evidence",
    "precedent_reference",
    "procedure_guide",
    "unknown",
]


class Fact(BaseModel):
    field: str
    value: Any
    source_type: FactSourceType = "USER_STATED"
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
    effective_to: date | None = None
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
    # tokens: 전체 청크를 corpus 빌드 시점에 형태소 분석한 결과(검색 인덱스의 기준).
    # stems: cases/products/guides 청크만 오프라인 precompute한 어간 부스트 신호.
    # tokens가 이미 형태소라 stems가 추가로 기여하는지는 아직 측정하지 않았다.
    tokens: list[str] | None = None
    stems: list[str] = Field(default_factory=list)


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
    routing_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    routing_method: RoutingMethod = "manual"


class CaseAnalyzeRequest(BaseModel):
    case_id: str | None = None
    session_id: str | None = None
    customer_id: str | None = "CUST-001"
    prompt: str = Field(min_length=1)
    as_of: date | None = None
    issues: list[IssueInput] = Field(default_factory=list)


class FactProvenanceEntry(BaseModel):
    field: str
    value: Any
    source_type: FactSourceType
    source_ref: str | None = None
    status: Literal["confirmed", "conflict", "unresolved"] = "confirmed"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class FactResolution(BaseModel):
    latest: dict[str, Fact] = Field(default_factory=dict)
    conflicts: dict[str, list[str]] = Field(default_factory=dict)
    provenance: dict[str, list[FactProvenanceEntry]] = Field(default_factory=dict)


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
    # 민원 유형별 고정 목록(report_composer.DOCUMENTS_BY_ISSUE). LLM이 아니라
    # 사람이 검토한 값만 나가야 사용자가 없는 서류를 찾아 헛걸음하지 않는다.
    documents_to_prepare: list[str] = Field(default_factory=list)
    # 검색된 근거가 이 민원에 어떤 의미인지 설명하는 줄글. 화면에 chunk 목록과 파일
    # 경로만 나열하면 소비자가 읽을 수 없어서, 사람이 부르는 문서 이름으로 풀어 쓴다.
    evidence_summary: str = ""
    generated_by: Literal["llm", "fallback"] = "fallback"
    compliance_blocked: bool = False
    compliance_flags: list[str] = Field(default_factory=list)
    compliance_reason: str = ""


class SupportChain(BaseModel):
    claim: str
    supporting_evidence: list[str] = Field(default_factory=list)
    inference_type: InferenceType = "unverified"
    evidence_role: EvidenceRole = "unknown"
    allowed_in_final: bool = False


class LogicVerification(BaseModel):
    summary: str = ""
    checks: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    support_chains: list[SupportChain] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    generated_by: Literal["llm", "fallback"] = "fallback"


class IssueAnalysis(BaseModel):
    issue_id: str
    product: str
    issue_type: str
    routing_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    routing_method: RoutingMethod = "manual"
    focal: dict[str, Any] = Field(default_factory=dict)
    target: dict[str, Any] = Field(default_factory=dict)
    mock_data: dict[str, Any] = Field(default_factory=dict)
    facts: list[Fact] = Field(default_factory=list)
    missing_facts: list[str] = Field(default_factory=list)
    fact_resolution: FactResolution
    retrieval_query: str = ""
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    decision: Decision
    risk_level: RiskLevel = "low"
    risk_reasons: list[str] = Field(default_factory=list)
    human_review_required: bool = False
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


class DecisionAuditLog(BaseModel):
    """구조화된 결정 감시 로그 - 모든 판정마다 기록"""
    audit_id: str
    case_id: str
    issue_id: str
    event_type: Literal["decision_gate", "fact_resolution", "logic_verification", "content_scope"] = "decision_gate"
    created_at: datetime
    decision: Control
    prior_control: Control | None = None
    risk_flags: list[str] = Field(default_factory=list)
    applied_rules: list[str] = Field(default_factory=list)
    confidence_score: float | None = None
    false_negative_risk: Literal["low", "medium", "high"] = "low"
    false_negative_indicators: list[str] = Field(default_factory=list)
    supporting_evidence: dict[str, Any] = Field(default_factory=dict)
    reviewed_by: str | None = None
    review_note: str = ""


class IssueValidationLog(BaseModel):
    """복합 민원 분리 검증 로그"""
    validation_id: str
    case_id: str
    total_issues: int
    validation_checks: list[str] = Field(default_factory=list)
    conflicts_detected: list[str] = Field(default_factory=list)
    causality_chains: list[list[str]] = Field(default_factory=list)
    duplicates_found: list[str] = Field(default_factory=list)
    corrections_applied: list[str] = Field(default_factory=list)
    created_at: datetime
    is_valid: bool = True
    severity: Literal["clean", "warning", "critical"] = "clean"



class ReviewQueueItem(BaseModel):
    case_id: str
    issue_id: str
    product: str
    issue_type: str
    control: Control
    risk_level: RiskLevel
    risk_reasons: list[str] = Field(default_factory=list)
    routing_confidence: float | None = None
    routing_method: RoutingMethod
