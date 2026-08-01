from __future__ import annotations

from datetime import date
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
    content_type: str = "text"
    parse_status: str = "ok"
    risk_flags: list[str] = Field(default_factory=list)


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
    content_type: str = "text"
    parse_status: str = "ok"
    risk_flags: list[str] = Field(default_factory=list)


class IssueInput(BaseModel):
    issue_id: str
    product: str
    issue_type: str
    text: str = Field(min_length=1)
    focal: dict[str, Any] = Field(default_factory=dict)
    target: dict[str, Any] = Field(default_factory=dict)
    facts: list[Fact] = Field(default_factory=list)
    required_facts: list[str] = Field(default_factory=list)


class CaseAnalyzeRequest(BaseModel):
    case_id: str | None = None
    session_id: str | None = None
    prompt: str = Field(min_length=1)
    as_of: date | None = None
    issues: list[IssueInput] = Field(default_factory=list)


class FactResolution(BaseModel):
    latest: dict[str, Fact] = Field(default_factory=dict)
    conflicts: dict[str, list[str]] = Field(default_factory=dict)


class Decision(BaseModel):
    control: Control
    risk_flags: list[str] = Field(default_factory=list)


class IssueAnalysis(BaseModel):
    issue_id: str
    product: str
    issue_type: str
    focal: dict[str, Any] = Field(default_factory=dict)
    target: dict[str, Any] = Field(default_factory=dict)
    facts: list[Fact] = Field(default_factory=list)
    missing_facts: list[str] = Field(default_factory=list)
    fact_resolution: FactResolution
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    decision: Decision
    content_scope: dict[str, Any] = Field(default_factory=dict)
    next_steps: list[str] = Field(default_factory=list)


class CaseAnalysis(BaseModel):
    case_id: str
    session_id: str | None = None
    prompt: str
    issues: list[IssueAnalysis]
