from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from server.agents.decision_gate import apply_decision_gate
from server.agents.focal_builder import REQUIRED_FACTS_BY_ISSUE
from server.agents.question_builder import expected_interest_question
from server.schemas import CaseAnalysis, EvidenceRef, Fact, IssueAnalysis


STATUS_LABELS = {
    "proceed": "진행 중",
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
    "금리변경미통지": ["상품설명서", "금리 변경 안내 자료", "우대조건 안내 자료"],
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

QUESTION_TEMPLATES_BY_FIELD: dict[str, tuple[str, str]] = {
    "가입일": ("상품에 가입한 날짜가 언제인지 알려주세요.", "가입 당시 적용된 약관과 안내 자료를 같은 기준일로 맞춰 확인하기 위해 필요합니다."),
    "상품명": ("가입한 상품의 정확한 이름을 알려주세요.", "상품별 약관과 우대조건이 달라서 근거 문서를 정확히 좁히기 위해 필요합니다."),
    "고객 인증·동의 데이터": ("본인 인증과 데이터 조회 동의를 완료했나요?", "고객 데이터를 조회해도 되는 상태인지 확인해야 실제 계약 정보와 민원을 연결할 수 있습니다."),
    "가상 계약 데이터": ("확인할 예금·적금 계좌번호를 알려주세요.", "시연용 계약 데이터와 사용자가 말한 상품을 정확히 연결하기 위해 필요합니다."),
    "금융회사명": ("거래한 금융회사 이름을 알려주세요.", "해당 금융회사 약관, 답변, 민원 접수 경로를 정확히 연결하기 위해 필요합니다."),
    "금융회사 답변": ("금융회사에서 받은 답변이나 안내 문구가 있다면 알려주세요.", "회사 측 설명과 약관 근거가 서로 맞는지 대조하기 위해 필요합니다."),
    "금융회사 답변 여부": ("금융회사에 문의한 적이 있다면 답변을 받았는지 알려주세요.", "회사 답변 전 단계인지, 분쟁조정 안내가 필요한 단계인지 구분하기 위해 필요합니다."),
    "금융회사 안내 내용": ("금융회사에서 안내받은 내용을 그대로 적어주세요.", "안내 내용이 약관이나 절차와 다른지 확인하기 위해 필요합니다."),
    "거래일": ("문제가 된 거래가 일어난 날짜를 알려주세요.", "거래일 기준으로 적용 약관과 처리 기한을 확인하기 위해 필요합니다."),
    "거래 금액": ("문제가 된 거래 금액이 얼마인지 알려주세요.", "피해 규모와 적용 가능한 처리 절차를 구분하기 위해 필요합니다."),
    "거부 사유 안내": ("거래가 거절되었을 때 받은 사유 안내가 있었나요?", "거절 사유가 약관상 제한 사유와 맞는지 확인하기 위해 필요합니다."),
    "거래 또는 계좌번호 마스킹본": ("거래내역이나 계좌번호는 뒷자리를 가린 상태로 알려주세요.", "본인 거래인지 확인하되 민감정보 노출을 줄이기 위해 필요합니다."),
    "인증 기록": ("본인인증 문자, 앱 알림, 로그인 기록이 있었는지 알려주세요.", "명의도용이나 비정상 인증 가능성을 먼저 확인하기 위해 필요합니다."),
    "인증일": ("본인인증이나 거래 인증이 이루어진 날짜를 알려주세요.", "인증 시점과 문제 발생 시점을 대조하기 위해 필요합니다."),
    "만기일": ("상품의 만기일이 언제인지 알려주세요.", "만기일 기준 지급 여부와 지연 여부를 판단하기 위해 필요합니다."),
    "안내 금액": ("예상하신 이자 금액은 얼마인가요?", "안내받은 금액과 실제 지급액의 차이를 계산하기 위해 필요합니다."),
    "안내받은 금리": ("가입할 때 안내받은 금리가 몇 퍼센트였는지 알려주세요.", "안내 금리와 실제 적용 금리가 다른지 확인하기 위해 필요합니다."),
    "실제 적용 금리": ("실제로 적용된 금리가 몇 퍼센트인지 알려주세요.", "적용 금리 오류 여부를 계산하기 위해 필요합니다."),
    "기본금리": ("상품의 기본금리가 몇 퍼센트였는지 알려주세요.", "기본금리와 우대금리 적용 여부를 나누어 확인하기 위해 필요합니다."),
    "우대금리": ("안내받은 우대금리가 몇 퍼센트였는지 알려주세요.", "우대조건 충족 시 받을 수 있었던 금리를 확인하기 위해 필요합니다."),
    "우대금리 조건": ("우대금리를 받기 위한 조건이 무엇이었는지 알려주세요.", "조건 충족 여부와 실제 적용 결과를 대조하기 위해 필요합니다."),
    "우대조건 상태": ("우대조건을 충족했다고 볼 만한 내역이 있는지 알려주세요.", "우대금리 미적용이 정당한지 판단하기 위해 필요합니다."),
    "설명서 수령 여부": ("상품설명서를 받았거나 확인했다는 기록이 있나요?", "중요 사항 설명과 교부 여부를 확인하기 위해 필요합니다."),
    "위험등급 안내 여부": ("상품 위험등급을 안내받았는지 알려주세요.", "위험상품 설명 의무가 지켜졌는지 확인하기 위해 필요합니다."),
    "원금손실 구조 안내 여부": ("원금 손실 가능성이나 구조를 안내받았는지 알려주세요.", "손실 가능성 설명이 충분했는지 확인하기 위해 필요합니다."),
    "금리 변경 이력": ("금리 변경 안내를 받은 날짜나 메시지가 있나요?", "변경 통지 여부와 실제 적용 시점을 대조하기 위해 필요합니다."),
    "안내 이력": ("금리 또는 우대조건 안내를 받은 기록이 있나요?", "사용자가 받은 안내와 상품 문서의 차이를 확인하기 위해 필요합니다."),
    "안내 수신 여부": ("문자, 앱 알림, 이메일 등으로 안내를 받았는지 알려주세요.", "통지 의무 이행 여부를 확인하기 위해 필요합니다."),
    "자동이체 실패일": ("자동이체가 실패한 날짜를 알려주세요.", "우대조건 미충족의 원인이 자동이체 실패인지 확인하기 위해 필요합니다."),
    "해지일": ("해지를 신청하거나 처리한 날짜를 알려주세요.", "중도해지 기준일과 적용 수수료를 확인하기 위해 필요합니다."),
    "해지 신청일": ("해지를 신청한 날짜를 알려주세요.", "신청일과 실제 처리일 사이 지연 여부를 확인하기 위해 필요합니다."),
    "해지 신청 내역": ("해지를 신청한 화면, 문자, 영업점 접수 기록이 있나요?", "해지 요청이 실제로 접수됐는지 확인하기 위해 필요합니다."),
    "위약금 또는 수수료 금액": ("차감된 위약금이나 수수료 금액을 알려주세요.", "약관상 수수료율과 실제 차감액이 맞는지 계산하기 위해 필요합니다."),
    "수수료 금액": ("차감된 수수료 금액을 알려주세요.", "수수료 고지와 실제 차감 내역을 비교하기 위해 필요합니다."),
    "수수료 안내 여부": ("수수료가 발생한다는 안내를 받았는지 알려주세요.", "수수료 고지 여부를 확인하기 위해 필요합니다."),
    "민원 접수일": ("민원을 접수한 날짜를 알려주세요.", "처리 기한이 지났는지 확인하기 위해 필요합니다."),
    "접수 채널": ("민원을 어디로 접수했는지 알려주세요.", "은행, 금감원, 소비자원 등 다음 안내 경로를 구분하기 위해 필요합니다."),
    "접수번호": ("민원 접수번호가 있다면 알려주세요.", "기존 접수 건과 후속 문의를 연결하기 위해 필요합니다."),
    "분쟁조정 안내 여부": ("분쟁조정 절차를 안내받았는지 알려주세요.", "다음 행동 안내가 누락됐는지 확인하기 위해 필요합니다."),
    "환매 신청일": ("환매를 신청한 날짜를 알려주세요.", "환매 기준일과 예정 지급일을 확인하기 위해 필요합니다."),
    "예정 지급일": ("안내받은 예정 지급일이 언제인지 알려주세요.", "지연 여부를 판단하기 위해 필요합니다."),
    "실제 지급일": ("실제로 돈이 지급된 날짜를 알려주세요.", "예정일과 실제 지급일 차이를 확인하기 위해 필요합니다."),
    "실제 지급 금액": ("실제로 지급받은 금액을 알려주세요.", "예상 금액과 실제 지급액 차이를 계산하기 위해 필요합니다."),
    "예상 상환금": ("안내받은 예상 상환금이 얼마였는지 알려주세요.", "안내 금액과 실제 상환 금액을 비교하기 위해 필요합니다."),
    "실제 상환금": ("실제로 상환받은 금액을 알려주세요.", "과소 지급 여부를 계산하기 위해 필요합니다."),
    "상환 내역": ("상환 내역이나 입금 내역을 알려주세요.", "상환 금액과 지급 시점을 확인하기 위해 필요합니다."),
    "배상 안내일": ("배상 안내를 받은 날짜를 알려주세요.", "배상 안내 기준과 이의제기 가능 시점을 확인하기 위해 필요합니다."),
    "제시 배상비율": ("제시받은 배상비율이 몇 퍼센트인지 알려주세요.", "배상 산정 근거와 적정성을 검토하기 위해 필요합니다."),
    "산정 근거 안내": ("배상비율 산정 근거를 안내받았는지 알려주세요.", "비율만 제시됐는지, 근거가 함께 제공됐는지 확인하기 위해 필요합니다."),
    "손실 금액": ("발생한 손실 금액을 알려주세요.", "손실 규모와 요구 조치를 구체화하기 위해 필요합니다."),
    "손실 산정 내역": ("손실 금액이 어떻게 계산됐는지 알 수 있는 내역이 있나요?", "손실 계산 방식과 약관 근거를 대조하기 위해 필요합니다."),
    "연체 발생일": ("연체가 발생한 날짜를 알려주세요.", "연체이자 적용 시작일을 확인하기 위해 필요합니다."),
    "연체이자": ("부과된 연체이자 금액을 알려주세요.", "연체이자 산정 방식이 맞는지 확인하기 위해 필요합니다."),
    "연체 내역": ("연체 내역이나 상환 기록을 알려주세요.", "연체 발생 원인과 기간을 확인하기 위해 필요합니다."),
    "대출 실행일": ("대출이 실행된 날짜를 알려주세요.", "대출 약정과 적용 금리를 기준일에 맞춰 확인하기 위해 필요합니다."),
    "기존 금리": ("변경 전 적용되던 금리를 알려주세요.", "금리 변경 전후 차이를 비교하기 위해 필요합니다."),
    "상환 예정 금액": ("안내받은 상환 예정 금액을 알려주세요.", "예정 금액과 실제 상환액 차이를 계산하기 위해 필요합니다."),
    "실제 상환 금액": ("실제로 상환한 금액을 알려주세요.", "상환금액 오류 여부를 확인하기 위해 필요합니다."),
    "중도상환일": ("중도상환한 날짜를 알려주세요.", "수수료 적용 기준일을 확인하기 위해 필요합니다."),
    "중도상환수수료": ("부과된 중도상환수수료 금액을 알려주세요.", "약정 수수료율과 실제 부과액을 비교하기 위해 필요합니다."),
}

PRIVACY_NOTICE = "주민등록번호, 전체 계좌번호, 카드번호, 인증번호, 비밀번호는 입력하거나 그대로 제출하지 마세요."
DISCLAIMER = "본 안내는 참고용 정보이며, 최종 판단은 금융감독원 분쟁조정 등 정식 절차를 통해 결정됩니다."

# 금융감독원 소비자지원부 분쟁조정 관련 안내
DISPUTE_RESOLUTION_INFO = {
    "title": "분쟁조정 신청 안내",
    "description": "본 분석 결과에 대해 이의가 있거나 추가 조정이 필요한 경우, 금융감독원 소비자지원부에 분쟁조정을 신청할 수 있습니다.",
    "visiting": {
        "address": "서울시 영등포구 국제금융로8길 26 KB국민은행 여의도 본점",
        "type": "방문민원 접수처",
    },
    "mail": {
        "address": "서울시 영등포구 의사당대로 141 KB국민은행 신관 소비자지원부",
        "type": "우편 접수처",
    },
    "contact": {
        "fax": "02-2047-9413",
        "email": "kbg734200@kbfg.com",
    },
    "documents_to_bring": {
        "myself": ["본인 실명입력증표"],
        "representative_consent": [
            "위임장(원서서식2호, 소비자보호포털의 민원관련서식에서 출력 가능)",
            "대리인 신분증 사본",
        ],
        "representative_family": [
            "위임장(원서서식2호, 소비자보호포털의 민원관련서식에서 출력 가능)",
            "대리인 신분증 사본",
            "주민등록증 사본 또는 가족관계증명서(발급일로부터 3개월 이내)",
        ],
        "representative_other": [
            "위임장(원서서식2호, 소비자보호포털의 민원관련서식에서 출력 가능)",
            "대리인 신분증 사본",
            "위임의 인감증명서 또는 본인서명사실확인서",
        ],
        "evidence": ["기타 사실관계를 입증하는 서류 사본"],
    },
}


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
    effective_to: str | None = None


class IssueResponseView(BaseModel):
    issue_id: str
    title: str
    product: str
    issue_type: str
    routing_confidence: float | None = None
    routing_method: str = "manual"
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
    risk_level: str = "low"
    risk_reasons: list[str] = Field(default_factory=list)
    decision_reasons: list[str] = Field(default_factory=list)


class CaseResponseView(BaseModel):
    case_id: str
    session_id: str | None = None
    issues: list[IssueResponseView]
    closing: dict[str, list[str] | str]
    dispute_resolution: dict[str, Any] = Field(default_factory=lambda: DISPUTE_RESOLUTION_INFO)


def compose_case_response(case: CaseAnalysis) -> CaseResponseView:
    issues = [compose_issue_response(issue) for issue in case.issues]
    return CaseResponseView(
        case_id=case.case_id,
        session_id=case.session_id,
        issues=issues,
        closing={
            "now": _collect_by_issue(issues, "next_steps"),
            "documents": _collect_documents_by_contract(case.issues, issues),
            "unconfirmed": _collect_questions(issues),
            "disclaimer": DISCLAIMER,
        },
        dispute_resolution=DISPUTE_RESOLUTION_INFO,
    )


def compose_issue_response(issue: IssueAnalysis) -> IssueResponseView:
    gate = apply_decision_gate(issue)
    status = gate.control
    return IssueResponseView(
        issue_id=issue.issue_id,
        title=f"{issue.product} / {issue.issue_type}",
        product=issue.product,
        issue_type=issue.issue_type,
        routing_confidence=issue.routing_confidence,
        routing_method=issue.routing_method,
        status=status,
        status_label=STATUS_LABELS[status],
        status_description=_status_description(issue, status),
        summary=_summary(issue),
        confirmed_facts=_confirmed_facts(issue.facts),
        missing_questions=_missing_questions(issue),
        evidence=[_evidence_item(ref) for ref in issue.evidence_refs],
        next_steps=_next_steps(issue, status),
        documents_to_prepare=_documents_to_prepare(issue),
        term_explanations=_term_explanations(issue),
        human_review=gate.human_review,
        risk_flags=issue.decision.risk_flags,
        risk_level=issue.risk_level,
        risk_reasons=issue.risk_reasons,
        decision_reasons=gate.supporting_reasons,
        masked_fields=_masked_fields(issue),
    )


def _status_for(issue: IssueAnalysis) -> str:
    return apply_decision_gate(issue).control


def _status_description(issue: IssueAnalysis, status: str) -> str:
    if status == "ask" and issue.missing_facts:
        return "다음 사실이 확인되어야 근거 검색과 판단을 이어갈 수 있습니다."
    return STATUS_DESCRIPTIONS[status]


def _summary(issue: IssueAnalysis) -> str:
    if issue.report.reasoning.strip():
        return issue.report.reasoning
    focal_type = issue.focal.get("type")
    if focal_type:
        return f"{issue.product}의 {issue.issue_type} 민원이며, 중심 확인 대상은 {focal_type}입니다."
    return f"{issue.product}의 {issue.issue_type} 민원입니다."


def _confirmed_facts(facts: list[Fact]) -> list[str]:
    visible_fields = {"date_or_duration", "amount", "rate", "product_name", "institution", "requested_action", "상품명", "가입일", "만기일", "기본금리", "우대금리", "실제 적용 금리", "가입금액", "세전 이자", "세금", "실제 지급 금액", "우대금리 조건", "우대조건 상태", "자동이체 실패일", "금리 변경 이력", "안내 이력", "안내 수신 여부"}
    return [f"{_field_label(fact.field)}: {fact.value}" for fact in facts if fact.field in visible_fields]


def _missing_questions(issue: IssueAnalysis) -> list[QuestionItem]:
    missing_facts = issue.missing_facts
    questions: list[QuestionItem] = []
    for field in missing_facts[:3]:
        question, reason = _question_for_missing_field(field, issue)
        questions.append(QuestionItem(field=field, question=question, reason=reason))
    return questions


def _question_for_missing_field(field: str, issue: IssueAnalysis) -> tuple[str, str]:
    if field == "안내 금액":
        question, reason = QUESTION_TEMPLATES_BY_FIELD[field]
        return expected_interest_question(issue.facts) or question, reason

    if field in QUESTION_TEMPLATES_BY_FIELD:
        return QUESTION_TEMPLATES_BY_FIELD[field]

    if field in REQUIRED_FACTS_BY_ISSUE.get(issue.issue_type, []):
        return (
            f"{field} 정보를 확인할 수 있는 내용이나 자료가 있나요?",
            f"{issue.issue_type} 쟁점에서 사실관계와 근거 문서를 연결하기 위해 필요합니다.",
        )

    return (
        f"{field} 정보를 추가로 알려주세요.",
        "누락된 사실을 확인해야 현재 근거로 안내 가능한 범위를 정할 수 있습니다.",
    )

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
        effective_to=ref.effective_to.isoformat() if ref.effective_to else None,
    )


def _next_steps(issue: IssueAnalysis, status: str) -> list[str]:
    if status in {"proceed", "ask"} and issue.report.follow_up_actions:
        return issue.report.follow_up_actions
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


def _collect_documents_by_contract(source_issues: list[IssueAnalysis], response_issues: list[IssueResponseView]) -> list[str]:
    grouped: dict[str, list[str]] = {}
    labels: dict[str, str] = {}

    for source, response in zip(source_issues, response_issues):
        key, label = _contract_group(source)
        labels[key] = label
        grouped.setdefault(key, [])
        for document in response.documents_to_prepare:
            _add_document(grouped[key], document)

    values: list[str] = []
    for key, documents in grouped.items():
        values.append(f"{labels[key]}: {', '.join(documents)}")
    return values


def _add_document(documents: list[str], candidate: str) -> None:
    """Add `candidate` unless it's already covered by an existing entry.

    DOCUMENTS_BY_ISSUE entries for different issue_types often name the same
    paperwork with different specificity ("상품설명서" vs "계약서 또는
    상품설명서") - exact-string dedup lets both through and the same document
    shows up twice in one contract's checklist. Treat substring containment
    either direction as the same requirement, keeping the more specific phrasing.
    """
    for index, existing in enumerate(documents):
        if candidate == existing or candidate in existing:
            return
        if existing in candidate:
            documents[index] = candidate
            return
    documents.append(candidate)


def _contract_group(issue: IssueAnalysis) -> tuple[str, str]:
    focal = issue.focal if isinstance(issue.focal, dict) else {}
    candidates = [
        focal.get("contract_id"),
        focal.get("account_id"),
        focal.get("account_number"),
        focal.get("product_name"),
        focal.get("shared_contract"),
        focal.get("contract"),
    ]
    identifier = next((str(value).strip() for value in candidates if str(value or "").strip()), "")

    date_value = (
        focal.get("contract_date")
        or focal.get("opened_at")
        or focal.get("가입일")
        or focal.get("date")
        or _fact_value(issue.facts, {"가입일", "contract_date", "date_or_duration"})
    )
    product_name = identifier or _fact_value(issue.facts, {"상품명", "product_name"}) or issue.product
    date_label = str(date_value).strip() if date_value else ""

    if identifier or date_label:
        key = f"{issue.product}|{product_name}|{date_label}"
        label = " / ".join(part for part in [issue.product, date_label, product_name] if part)
        return key, label

    return issue.issue_id, f"{issue.issue_id} {issue.product}"


def _fact_value(facts: list[Fact], fields: set[str]) -> str | None:
    for fact in facts:
        if fact.field in fields and str(fact.value).strip():
            return str(fact.value).strip()
    return None


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
        "상품명": "상품명",
        "가입일": "가입일",
        "만기일": "만기일",
        "기본금리": "기본금리",
        "우대금리": "우대금리",
        "실제 적용 금리": "실제 적용 금리",
        "가입금액": "가입금액",
        "세전 이자": "세전 이자",
        "세금": "세금",
        "실제 지급 금액": "실제 지급 금액",
        "우대금리 조건": "우대금리 조건",
        "우대조건 상태": "우대조건 상태",
        "자동이체 실패일": "자동이체 실패일",
        "금리 변경 이력": "금리 변경 이력",
        "안내 이력": "안내 이력",
        "안내 수신 여부": "안내 수신 여부",
    }.get(field, field)


def _title_from_path(path: str) -> str:
    return path.replace("\\", "/").split("/")[-1]
