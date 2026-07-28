from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from server.agent.decision_gate import apply_decision_gate
from server.schemas import CaseAnalysis, EvidenceRef, Fact, IssueAnalysis


STATUS_LABELS = {
    "proceed": "진행 가능",
    "amend": "보완 필요",
    "ask": "추가 확인 필요",
    "hold": "전문가 검토 대기",
}

STATUS_DESCRIPTIONS = {
    "proceed": "현재 확인된 정보와 근거를 바탕으로 다음 안내를 진행할 수 있습니다.",
    "amend": "민감정보 마스킹이나 증빙 정리가 먼저 필요합니다.",
    "ask": "핵심 사실이 부족하여 추가 확인이 필요합니다.",
    "hold": "고위험 또는 불확실성이 있어 자동 판단하지 않고 사람이 검토해야 합니다.",
}

TERM_EXPLANATIONS = {
    "우대금리": "기본 이율에 특정 조건을 충족했을 때 추가로 적용되는 이율입니다.",
    "환매": "펀드 등 투자상품을 다시 현금화하기 위해 매도 또는 지급을 신청하는 절차입니다.",
    "분쟁조정": "금융회사와 소비자 사이의 다툼을 정식 기관 절차로 조정받는 과정입니다.",
    "중도해지": "만기 전에 계약을 끝내는 절차입니다.",
    "명의도용": "본인의 동의 없이 본인 명의가 사용된 상황을 말합니다.",
}

DOCUMENTS_BY_ISSUE = {
    "계약해지_지연": ["계약서 또는 상품설명서", "해지 신청 기록", "금융회사 답변"],
    "금리적용오류": ["상품설명서", "가입 당시 안내 자료", "이자 지급 내역"],
    "인출제한": ["거래내역 또는 화면 캡처", "거부 사유 안내", "금융회사 답변"],
    "거래오류": ["거래내역서", "계산 근거", "상품설명서"],
    "명의도용": ["거래 또는 계좌 개설 알림", "본인 인증 기록", "금융회사 답변"],
    "만기지급거절": ["계약서 또는 상품설명서", "만기일 확인 자료", "금융회사 답변"],
    "우대금리설명부족": ["상품설명서", "우대금리 조건 안내 자료", "가입 당시 상담 기록"],
    "중도해지위약금": ["계약서 또는 상품설명서", "해지 신청 내역", "수수료 산정 내역"],
    "자동이체누락안내": ["자동이체 실패 내역", "우대조건 안내 자료", "알림 수신 내역"],
    "민원처리지연": ["민원 접수 내역", "접수번호", "금융회사 답변 또는 처리 상태"],
    "위험설명부족": ["상품설명서", "위험등급 안내 자료", "가입 당시 상담 기록"],
    "환매지연": ["환매 신청 내역", "예정 지급일 안내", "실제 지급 내역"],
    "수수료미고지": ["상품설명서", "수수료 차감 내역", "가입 당시 안내 자료"],
    "해지절차복잡": ["해지 문의 내역", "금융회사 안내 내용", "계약서 또는 상품설명서"],
    "손실민원부실": ["민원 접수 내역", "손실 관련 거래내역", "금융회사 답변"],
    "원금손실설명부족": ["상품설명서", "위험등급 안내 자료", "가입 당시 상담 기록"],
    "상환금과소지급": ["상환 내역", "상품설명서", "예상 상환금 안내 자료"],
    "배상비율불만": ["배상 안내문", "산정 근거 자료", "금융회사 답변"],
    "중도해지손실": ["중도해지 또는 상환 요청 내역", "손실 산정 내역", "상품설명서"],
    "분쟁조정안내부족": ["민원 접수 내역", "금융회사 답변", "분쟁조정 안내 자료"],
}

PRIVACY_NOTICE = "주민등록번호, 전체 계좌번호, 카드번호, 인증번호, 비밀번호는 입력하거나 그대로 제출하지 마세요."
DISCLAIMER = "본 안내는 참고용 정보이며, 최종 판단은 금융감독원 분쟁조정 등 정식 절차를 통해 결정됩니다."


class QuestionItem(BaseModel):
    field: str
    question: str
    reason: str


class EvidenceItem(BaseModel):
    doc_id: str
    chunk_id: str
    title: str
    page: int
    section: str | None = None
    score: float
    match_type: str = "full_text"
    snippet: str
    effective_from: str | None = None


class IssueResponseView(BaseModel):
    issue_id: str
    title: str
    product: str
    issue_type: str
    status: str
    status_label: str
    status_description: str
    summary: str
    confirmed_facts: list[str] = Field(default_factory=list)
    missing_questions: list[QuestionItem] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    documents_to_prepare: list[str] = Field(default_factory=list)
    term_explanations: list[str] = Field(default_factory=list)
    privacy_notice: str = PRIVACY_NOTICE
    masked_fields: list[str] = Field(default_factory=list)
    human_review: bool = False
    risk_flags: list[str] = Field(default_factory=list)
    decision_reasons: list[str] = Field(default_factory=list)


class CaseResponseView(BaseModel):
    case_id: str
    session_id: str | None = None
    issues: list[IssueResponseView]
    closing: dict[str, list[str] | str]


def compose_case_response(case: CaseAnalysis) -> CaseResponseView:
    issues = [compose_issue_response(issue) for issue in case.issues]
    return CaseResponseView(
        case_id=case.case_id,
        session_id=case.session_id,
        issues=issues,
        closing={
            "now": _collect_by_issue(issues, "next_steps"),
            "documents": _collect_by_issue(issues, "documents_to_prepare"),
            "unconfirmed": _collect_questions(issues),
            "disclaimer": DISCLAIMER,
        },
    )


def compose_issue_response(issue: IssueAnalysis) -> IssueResponseView:
    gate = apply_decision_gate(issue)
    status = gate.control
    return IssueResponseView(
        issue_id=issue.issue_id,
        title=f"{issue.product} / {issue.issue_type}",
        product=issue.product,
        issue_type=issue.issue_type,
        status=status,
        status_label=STATUS_LABELS[status],
        status_description=_status_description(issue, status),
        summary=_summary(issue),
        confirmed_facts=_confirmed_facts(issue.facts),
        missing_questions=_missing_questions(issue.missing_facts),
        evidence=[_evidence_item(ref) for ref in issue.evidence_refs],
        next_steps=_next_steps(issue, status),
        documents_to_prepare=_documents_to_prepare(issue),
        term_explanations=_term_explanations(issue),
        human_review=gate.human_review,
        risk_flags=issue.decision.risk_flags,
        decision_reasons=gate.supporting_reasons,
        masked_fields=_masked_fields(issue),
    )


def _status_for(issue: IssueAnalysis) -> str:
    return apply_decision_gate(issue).control


def _status_description(issue: IssueAnalysis, status: str) -> str:
    if status == "hold" and issue.target.get("support_status") == "unsupported":
        return "현재 지원 범위에 없는 상품이라 자동 답변하지 않고 Human Review로 보냅니다."
    if status == "ask" and issue.missing_facts:
        return "다음 사실이 확인되어야 근거 검색과 판단을 이어갈 수 있습니다."
    return STATUS_DESCRIPTIONS[status]


def _summary(issue: IssueAnalysis) -> str:
    focal_type = issue.focal.get("type")
    if focal_type:
        return f"{issue.product}의 {issue.issue_type} 민원이며, 중심 확인 대상은 {focal_type}입니다."
    return f"{issue.product}의 {issue.issue_type} 민원입니다."


def _confirmed_facts(facts: list[Fact]) -> list[str]:
    visible_fields = {"date_or_duration", "amount", "rate", "product_name", "institution", "requested_action"}
    return [f"{_field_label(fact.field)}: {fact.value}" for fact in facts if fact.field in visible_fields]


def _missing_questions(missing_facts: list[str]) -> list[QuestionItem]:
    return [
        QuestionItem(
            field=field,
            question=f"{field}을(를) 알려주세요.",
            reason="검색 근거와 사실관계를 같은 민원에 연결하기 위해 필요합니다.",
        )
        for field in missing_facts[:3]
    ]


def _evidence_item(ref: EvidenceRef) -> EvidenceItem:
    return EvidenceItem(
        doc_id=ref.doc_id,
        chunk_id=ref.chunk_id,
        title=_title_from_path(ref.path),
        page=ref.page,
        section=ref.section,
        score=ref.score,
        match_type=ref.match_type,
        snippet=ref.snippet,
        effective_from=ref.effective_from.isoformat() if ref.effective_from else None,
    )


def _next_steps(issue: IssueAnalysis, status: str) -> list[str]:
    if status == "hold":
        return ["자동 답변으로 단정하지 않고 Human Review에서 사실관계와 위험 신호를 확인합니다."]
    if status == "ask":
        return issue.next_steps or ["부족한 정보를 추가한 뒤 다시 분석합니다."]
    if status == "amend":
        return ["민감정보를 마스킹하고 증빙 범위를 정리한 뒤 다시 확인합니다."]
    return issue.next_steps or ["근거 문서와 확인된 사실을 바탕으로 안내문 초안을 검토합니다."]


def _documents_to_prepare(issue: IssueAnalysis) -> list[str]:
    return DOCUMENTS_BY_ISSUE.get(issue.issue_type, ["계약서 또는 상품설명서", "금융회사 답변", "거래내역"])


def _term_explanations(issue: IssueAnalysis) -> list[str]:
    text = f"{issue.issue_type} {issue.focal} {issue.next_steps}"
    return [f"{term}: {explanation}" for term, explanation in TERM_EXPLANATIONS.items() if term in text]


def _masked_fields(issue: IssueAnalysis) -> list[str]:
    focal_scope = issue.focal.get("content_scope") if isinstance(issue.focal.get("content_scope"), dict) else {}
    values = list(issue.content_scope.get("masked_fields") or []) + list(focal_scope.get("masked_fields") or [])
    return list(dict.fromkeys(values))


def _collect_by_issue(issues: list[IssueResponseView], field: str) -> list[str]:
    values: list[str] = []
    for issue in issues:
        for value in getattr(issue, field):
            values.append(f"{issue.issue_id}: {value}")
    return values


def _collect_questions(issues: list[IssueResponseView]) -> list[str]:
    values: list[str] = []
    for issue in issues:
        for item in issue.missing_questions:
            values.append(f"{issue.issue_id}: {item.question}")
    return values


def _field_label(field: str) -> str:
    return {
        "date_or_duration": "날짜 또는 기간",
        "amount": "금액",
        "rate": "금리 또는 비율",
        "product_name": "상품명",
        "institution": "금융회사",
        "requested_action": "요청 조치",
    }.get(field, field)


def _title_from_path(path: str) -> str:
    return path.replace("\\", "/").split("/")[-1]
