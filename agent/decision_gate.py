from __future__ import annotations

from pydantic import BaseModel, Field

from server.schemas import IssueAnalysis


CONTROL_PRIORITY = {"proceed": 0, "amend": 1, "ask": 2, "hold": 3}
HIGH_RISK_ISSUES = {"명의도용", "지원제외_대출"}
HOLD_RISK_FLAGS = {"fact_conflict", "identity_theft", "unauthorized_transaction", "fraud_suspected"}
AMEND_RISK_FLAGS = {"pii_detected", "masking_required", "scope_review_required"}


class GateDecision(BaseModel):
    control: str
    reasons: list[str] = Field(default_factory=list)
    supporting_reasons: list[str] = Field(default_factory=list)
    human_review: bool = False


def apply_decision_gate(issue: IssueAnalysis) -> GateDecision:
    """Apply B's conservative policy over A's baseline decision.

    A returns a deterministic server-side baseline. B applies product support,
    safety, target clarity, and content-scope policy before composing a user
    response.
    """
    candidates: list[GateDecision] = [
        GateDecision(control=issue.decision.control, reasons=["A API baseline decision"])
    ]

    if issue.target.get("support_status") == "unsupported":
        candidates.append(
            GateDecision(
                control="hold",
                reasons=["현재 지원 범위에 없는 상품이므로 Human Review가 필요합니다."],
                human_review=True,
            )
        )
    if issue.issue_type in HIGH_RISK_ISSUES:
        candidates.append(
            GateDecision(
                control="hold",
                reasons=["명의도용 또는 지원 제외 유형은 자동 판단하지 않습니다."],
                human_review=True,
            )
        )
    if HOLD_RISK_FLAGS & set(issue.decision.risk_flags):
        candidates.append(
            GateDecision(
                control="hold",
                reasons=["사실 충돌 또는 고위험 신호가 있어 사람이 확인해야 합니다."],
                human_review=True,
            )
        )
    if issue.target.get("is_unclear") is True:
        candidates.append(GateDecision(control="ask", reasons=["처리 대상 금융회사 또는 접수 대상이 불명확합니다."]))
    if issue.missing_facts:
        candidates.append(GateDecision(control="ask", reasons=["핵심 사실이 부족합니다."]))
    if "evidence_insufficient" in issue.decision.risk_flags and not issue.evidence_refs:
        candidates.append(GateDecision(control="ask", reasons=["검색 근거가 부족합니다."]))
    if AMEND_RISK_FLAGS & set(issue.decision.risk_flags) or _requires_user_confirmation(issue):
        candidates.append(GateDecision(control="amend", reasons=["개인정보 마스킹 또는 제출 범위 확인이 필요합니다."]))

    decision = max(candidates, key=lambda item: CONTROL_PRIORITY[item.control])
    same_level_reasons = [reason for item in candidates if item.control == decision.control for reason in item.reasons]
    all_reasons = [reason for item in candidates for reason in item.reasons]
    return GateDecision(
        control=decision.control,
        reasons=_dedupe(same_level_reasons),
        supporting_reasons=_dedupe(all_reasons),
        human_review=decision.human_review or decision.control == "hold",
    )


def _requires_user_confirmation(issue: IssueAnalysis) -> bool:
    focal_scope = issue.focal.get("content_scope") if isinstance(issue.focal.get("content_scope"), dict) else {}
    return bool(
        issue.content_scope.get("requires_user_confirmation")
        or issue.content_scope.get("masked_fields")
        or focal_scope.get("requires_user_confirmation")
        or focal_scope.get("masked_fields")
    )


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
