from __future__ import annotations

import re
from typing import Literal

from server.agents.content_scope import apply_content_scope
from server.schemas import Fact, IssueInput


SUPPORTED_PRODUCTS = {"예금", "적금", "대출", "펀드", "ELS", "공통"}
UNSUPPORTED_PRODUCTS = {"보험"}

INSTITUTION_KEYWORDS = (
    "국민은행",
    "KB국민은행",
    "KB",
    "신한은행",
    "하나은행",
    "우리은행",
    "농협",
    "카카오뱅크",
    "토스뱅크",
)

REQUIRED_FACTS_BY_ISSUE: dict[str, list[str]] = {
    "계약해지_지연": ["가입일", "상품명", "해지 신청일", "금융회사 답변"],
    "금리적용오류": ["가입일", "상품명", "안내받은 금리", "실제 적용 금리"],
    "인출제한": ["거래일", "금융회사명", "거래 금액", "거부 사유 안내"],
    "거래오류": ["거래일", "상품명", "안내 금액", "실제 지급 금액"],
    "명의도용": ["인지일", "금융회사명", "거래 또는 계좌번호 마스킹본", "인증 기록", "금융회사 답변"],
    "만기지급거절": ["가입일", "만기일", "상품명", "금융회사 답변"],
    "우대금리설명부족": ["가입일", "상품명", "우대금리 조건", "설명서 수령 여부"],
    "금리변경미통지": ["상품명", "기본금리", "실제 적용 금리", "금리 변경 이력", "안내 이력"],
    "중도해지위약금": ["가입일", "해지일", "상품명", "위약금 또는 수수료 금액"],
    "자동이체누락안내": ["자동이체 실패일", "상품명", "안내 수신 여부", "우대금리 조건"],
    "민원처리지연": ["민원 접수일", "접수 채널", "금융회사 답변 여부"],
    "위험설명부족": ["가입일", "상품명", "설명서 수령 여부", "위험등급 안내 여부"],
    "환매지연": ["환매 신청일", "상품명", "예정 지급일", "실제 지급일"],
    "수수료미고지": ["가입일", "상품명", "수수료 금액", "설명서 수령 여부"],
    "해지절차복잡": ["해지 문의일", "상품명", "금융회사 안내 내용"],
    "손실민원부실": ["민원 접수일", "상품명", "손실 금액", "금융회사 답변"],
    "원금손실설명부족": ["가입일", "상품명", "설명서 수령 여부", "원금손실 구조 안내 여부"],
    "상환금과소지급": ["가입일", "만기일 또는 조기상환일", "상품명", "예상 상환금", "실제 상환금"],
    "배상비율불만": ["배상 안내일", "상품명", "제시 배상비율", "산정 근거 안내"],
    "중도해지손실": ["가입일", "해지 또는 상환 요청일", "상품명", "손실 금액"],
    "분쟁조정안내부족": ["민원 접수일", "상품명", "금융회사 답변", "분쟁조정 안내 여부"],
    "대출금리변경미통지": ["대출 실행일", "상품명", "기존 금리", "실제 적용 금리", "금리 변경 이력", "안내 이력"],
    "상환금액오류": ["대출 실행일", "상품명", "상환 예정 금액", "실제 상환 금액", "상환 내역"],
    "중도상환수수료": ["대출 실행일", "상품명", "중도상환일", "중도상환수수료", "수수료 안내 여부"],
    "연체이자산정": ["상품명", "연체 발생일", "연체이자", "연체 내역", "금융회사 답변"],
    "지원제외_보험": ["Human Review"],
}

# missing_facts()가 문자열 완전일치로 대조하므로, required_facts에는 이 어휘만 들어와야 한다.
KNOWN_FACT_FIELDS: frozenset[str] = frozenset(
    field for fields in REQUIRED_FACTS_BY_ISSUE.values() for field in fields
) | {"상품 유형", "사건일"}

FOCAL_TYPES_BY_ISSUE = {
    "계약해지_지연": "contract",
    "금리적용오류": "terms_or_notice",
    "인출제한": "transaction",
    "거래오류": "transaction_statement",
    "명의도용": "identity_or_auth_record",
    "만기지급거절": "contract",
    "우대금리설명부족": "notice",
    "금리변경미통지": "rate_change_notice",
    "중도해지위약금": "contract",
    "자동이체누락안내": "notice",
    "민원처리지연": "company_response",
    "위험설명부족": "product_disclosure",
    "환매지연": "transaction",
    "수수료미고지": "fee_notice",
    "해지절차복잡": "procedure_notice",
    "손실민원부실": "company_response",
    "원금손실설명부족": "product_disclosure",
    "상환금과소지급": "settlement_statement",
    "배상비율불만": "company_response",
    "중도해지손실": "settlement_statement",
    "분쟁조정안내부족": "procedure_notice",
    "대출금리변경미통지": "rate_change_notice",
    "상환금액오류": "settlement_statement",
    "중도상환수수료": "fee_notice",
    "연체이자산정": "settlement_statement",
}

DATE_RE = re.compile(r"\d{4}[-.]\d{1,2}[-.]\d{1,2}|\d{1,2}월\s*\d{1,2}일|\d+일째|\d+일")
AMOUNT_RE = re.compile(r"\d[\d,]*(?:만\s*)?원")
RATE_RE = re.compile(r"\d+(?:\.\d+)?%p?|\d+(?:\.\d+)?퍼센트")


def build_issue_input(
    *,
    issue_id: str,
    product: str,
    issue_type: str,
    text: str,
    raw_product: str | None = None,
    routing_method: Literal["llm", "rules", "manual"] = "manual",
    routing_confidence: float | None = None,
) -> IssueInput:
    raw_product = raw_product or product
    product_for_api = product if product in SUPPORTED_PRODUCTS else "공통"
    scope = apply_content_scope(text)
    scoped_text = scope.text
    facts = extract_facts(scoped_text)
    required_facts = required_facts_for(product_for_api, issue_type)
    facts = _add_contextual_amount_facts(scoped_text, facts, required_facts)

    return IssueInput(
        issue_id=issue_id,
        product=product_for_api,
        issue_type=issue_type,
        text=scoped_text,
        focal=build_focal(product_for_api, issue_type, scoped_text, facts, raw_product, scope.as_dict()),
        target=build_target(scoped_text, raw_product),
        facts=facts,
        required_facts=required_facts,
        routing_method=routing_method,
        routing_confidence=routing_confidence,
    )


def build_focal(
    product: str,
    issue_type: str,
    text: str,
    facts: list[Fact],
    raw_product: str | None,
    content_scope: dict | None = None,
) -> dict:
    dates = [str(fact.value) for fact in facts if fact.field == "date_or_duration"]
    amounts = [str(fact.value) for fact in facts if fact.field == "amount"]
    rates = [str(fact.value) for fact in facts if fact.field == "rate"]
    product_name = _fact_value(facts, "product_name")
    institution = _fact_value(facts, "institution")
    focal = {
        "source": "agent.focal_builder",
        "type": FOCAL_TYPES_BY_ISSUE.get(issue_type, "user_statement"),
        "primary_object": _primary_object(product, issue_type),
        "event": issue_type,
        "text_span": text,
        "product_name": product_name,
        "institution": institution,
        "key_dates": dates,
        "amounts": amounts,
        "rates": rates,
        "source_refs": ["user_input"],
        "content_scope": content_scope or {},
    }
    if raw_product in UNSUPPORTED_PRODUCTS:
        focal["unsupported_product"] = raw_product
        focal["type"] = "human_review"
    return focal


def build_target(text: str, raw_product: str | None) -> dict:
    institution = _extract_institution(text)
    if raw_product in UNSUPPORTED_PRODUCTS:
        return {
            "subject": "Human Review",
            "action_target": None,
            "is_unclear": False,
            "reason": f"{raw_product}은 현재 자동 분석 지원 범위가 아닙니다.",
            "support_status": "unsupported",
        }
    if institution:
        return {
            "subject": institution,
            "action_target": f"{institution} 민원창구",
            "is_unclear": False,
            "reason": None,
            "support_status": "supported",
        }
    return {
        "subject": "금융회사",
        "action_target": None,
        "is_unclear": True,
        "reason": "금융회사명이 확인되지 않아 접수 대상을 확정하지 않았습니다.",
        "support_status": "supported",
    }


def extract_facts(text: str) -> list[Fact]:
    facts = [Fact(field="user_statement", value=text, source_ref="user_input", confidence=0.75)]
    for value in DATE_RE.findall(text):
        facts.append(Fact(field="date_or_duration", value=value, source_ref="user_input", confidence=0.7))
    for value in AMOUNT_RE.findall(text):
        facts.append(Fact(field="amount", value=value, source_ref="user_input", confidence=0.75))
    for value in RATE_RE.findall(text):
        facts.append(Fact(field="rate", value=value, source_ref="user_input", confidence=0.75))

    product_name = _extract_product_name(text)
    if product_name:
        facts.append(Fact(field="product_name", value=product_name, source_ref="user_input", confidence=0.6))
    institution = _extract_institution(text)
    if institution:
        facts.append(Fact(field="institution", value=institution, source_ref="user_input", confidence=0.65))
    action = _extract_requested_action(text)
    if action:
        facts.append(Fact(field="requested_action", value=action, source_ref="user_input", confidence=0.6))
    return facts


def _add_contextual_amount_facts(text: str, facts: list[Fact], required: list[str]) -> list[Fact]:
    required_set = set(required)
    if not {"안내 금액", "실제 지급 금액"} <= required_set:
        return facts

    amount_facts = [fact for fact in facts if fact.field == "amount"]
    matches = list(AMOUNT_RE.finditer(text))
    added: set[str] = set()
    for match, fact in zip(matches, amount_facts):
        prefix = text[max(0, match.start() - 24):match.start()]
        suffix = text[match.end():min(len(text), match.end() + 18)]
        field = None
        if re.search(r"가입\s*금액|원금", prefix):
            field = "가입금액"
        elif re.search(r"예상|기대", suffix):
            field = "안내 금액"
        elif re.search(r"실제|입금|지급", prefix + suffix):
            field = "실제 지급 금액"
        if field in required_set and field not in added:
            facts.append(fact.model_copy(update={"field": field, "value": _normalize_amount(fact.value)}))
            added.add(field)
    return facts


def _normalize_amount(value: object) -> int | float | object:
    text = str(value).replace(",", "").replace("원", "").replace(" ", "")
    if text.isdigit():
        return int(text)
    total = 0.0
    for unit, multiplier in (("억", 100_000_000), ("천만", 10_000_000), ("백만", 1_000_000), ("만", 10_000), ("천", 1_000), ("백", 100)):
        match = re.search(rf"(\d+(?:\.\d+)?)\s*{unit}", text)
        if match:
            total += float(match.group(1)) * multiplier
    return int(total) if total.is_integer() else total if total else value


def required_facts_for(product: str, issue_type: str) -> list[str]:
    if issue_type in REQUIRED_FACTS_BY_ISSUE:
        return list(REQUIRED_FACTS_BY_ISSUE[issue_type])
    if product == "공통" or issue_type == "미분류":
        return ["상품 유형", "사건일", "금융회사 답변"]
    return ["가입일", "상품명", "사건일", "금융회사 답변"]


def _extract_institution(text: str) -> str | None:
    return next((keyword for keyword in INSTITUTION_KEYWORDS if keyword in text), None)


def _extract_product_name(text: str) -> str | None:
    match = re.search(r"([가-힣A-Za-z0-9·\-\(\)]+(?:예금|적금|펀드|ELS))", text)
    return match.group(1) if match else None


def _extract_requested_action(text: str) -> str | None:
    if any(keyword in text for keyword in ("해지", "환매", "상환")):
        return "계약 또는 거래 처리"
    if any(keyword in text for keyword in ("설명", "안내", "산정 기준")):
        return "설명 또는 근거 확인"
    if any(keyword in text for keyword in ("인출", "출금", "지급")):
        return "지급 또는 거래 제한 확인"
    if any(keyword in text for keyword in ("민원", "분쟁조정")):
        return "민원 또는 분쟁조정 절차 확인"
    return None


def _fact_value(facts: list[Fact], field: str) -> str | None:
    return next((str(fact.value) for fact in facts if fact.field == field), None)


def _primary_object(product: str, issue_type: str) -> str:
    if issue_type.startswith("지원제외"):
        return issue_type
    return f"{product} {issue_type}" if issue_type != "미분류" else product
