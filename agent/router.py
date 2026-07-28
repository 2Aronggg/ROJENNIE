from __future__ import annotations

import re
from datetime import date

from agent.focal_builder import build_issue_input
from server.schemas import CaseAnalyzeRequest, IssueInput


PRODUCT_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ELS", ("ELS", "지수연계")),
    ("펀드", ("펀드", "환매", "운용보수", "보수")),
    ("보험", ("보험", "보험금", "환급금")),
    ("적금", ("적금", "자동이체", "우대조건")),
    ("예금", ("예금", "정기예금", "계좌", "통장", "지급정지")),
)

ISSUE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("명의도용", ("명의도용", "모르는", "신청한 적", "본인인증 없이", "저도 모르는 사이", "내가 신청하지 않은", "비인가")),
    ("계약해지_지연", ("해지 신청", "해지하려", "해지하러", "처리가 안", "처리를 안", "미뤄지고")),
    ("금리적용오류", ("우대금리를", "낮게 적용", "금리라고 들", "다르게 계산", "지급된 이자")),
    ("인출제한", ("인출", "출금", "지급정지", "못 찾고", "거부")),
    ("거래오류", ("거래내역", "만기 지급액", "이자 금액", "계산한 것", "차이가")),
    ("만기지급거절", ("만기", "지급을 안", "지급 처리가", "지급을 미루")),
    ("우대금리설명부족", ("우대금리", "우대조건", "조건을 제대로 설명", "안내를 못 받", "만기 때가 돼서야")),
    ("중도해지위약금", ("중도해지", "위약금", "계약서에 없던 수수료")),
    ("자동이체누락안내", ("자동이체", "이체 실패", "우대조건이 깨졌", "우대금리 0.5%를 놓쳤")),
    ("민원처리지연", ("민원", "문의", "답변이 없", "확인 중", "처리 상태")),
    ("위험설명부족", ("위험등급", "원금손실 위험", "손실 가능성", "위험에 대한 설명")),
    ("환매지연", ("환매", "환매금", "지연되고")),
    ("수수료미고지", ("수수료", "보수", "차감", "빠져나갔")),
    ("해지절차복잡", ("해지 신청 방법", "절차가 너무 복잡", "절차 안내")),
    ("손실민원부실", ("손실 원인", "손실 관련", "손실에 대한 민원", "답변이 형식적", "원론적인")),
    ("원금손실설명부족", ("ELS", "원금손실", "기초자산", "예금처럼 안전")),
    ("상환금과소지급", ("상환금", "조기상환", "만기 정산", "부족해")),
    ("배상비율불만", ("배상 비율", "배상비율", "산정 기준", "배상 협상")),
    ("중도해지손실", ("조기해지", "중도 해지", "중도상환", "손실 규모", "손실이")),
    ("분쟁조정안내부족", ("분쟁조정", "금감원", "신청 절차")),
    ("금리인상미통지", ("금리가", "금리", "인상 안내", "사전 안내")),
    ("설명의무위반", ("상품 설명", "조건에 대한 설명", "서류만 작성", "산정 기준을 설명")),
)

SPLIT_RE = re.compile(r"(?:[.!?。]\s+)|(?:요\.\s+)|(?:니다\.\s+)|\s*(?:아 그리고|그리고 마지막으로|그런데|게다가|또|그리고)\s*")


def build_case_request(
    prompt: str,
    *,
    case_id: str | None = None,
    session_id: str | None = None,
    as_of: date | None = None,
) -> CaseAnalyzeRequest:
    """Build the A-server analyze payload with explicit issues.

    B must not call A with an empty ``issues`` list because A will fall back to
    ``미분류`` and lexical retrieval becomes weak.
    """
    return CaseAnalyzeRequest(
        case_id=case_id,
        session_id=session_id,
        prompt=prompt,
        as_of=as_of,
        issues=split_prompt_to_issues(prompt),
    )


def split_prompt_to_issues(prompt: str) -> list[IssueInput]:
    spans = _issue_spans(prompt)
    return [_build_issue(index, span) for index, span in enumerate(spans, start=1)]


def _issue_spans(prompt: str) -> list[str]:
    raw_parts = [part.strip(" \t\r\n.,") for part in SPLIT_RE.split(prompt) if part and part.strip(" \t\r\n.,")]
    if not raw_parts:
        return [prompt.strip()]

    spans: list[str] = []
    current = ""
    for part in raw_parts:
        if current and _has_new_issue_signal(part):
            spans.append(current)
            current = part
        else:
            current = f"{current}. {part}" if current else part
    if current:
        spans.append(current)
    return spans


def _build_issue(index: int, text: str) -> IssueInput:
    raw_product = _classify_product(text)
    issue_type = _classify_issue_type(text, raw_product)
    raw_product = raw_product or _infer_product_from_issue(issue_type)
    return build_issue_input(
        issue_id=f"issue_{index:03d}",
        product=raw_product or "공통",
        issue_type=issue_type,
        text=text,
        raw_product=raw_product,
    )


def _has_new_issue_signal(text: str) -> bool:
    if _classify_product(text) is None and text.startswith(("신청한 적", "벌써", "10일째", "14일째")):
        return False
    return _classify_product(text) is not None or _classify_issue_type(text, None) != "미분류"


def _classify_product(text: str) -> str | None:
    return next((product for product, keywords in PRODUCT_KEYWORDS if any(keyword in text for keyword in keywords)), None)


def _classify_issue_type(text: str, product: str | None) -> str:
    if product == "보험":
        return "지원제외_보험"
    if product == "적금" and any(keyword in text for keyword in ("자동이체", "이체 실패", "우대조건이 깨졌", "놓쳤")):
        return "자동이체누락안내"
    if product == "적금" and any(keyword in text for keyword in ("중도해지", "위약금", "계약서에 없던 수수료")):
        return "중도해지위약금"
    if product == "적금" and any(keyword in text for keyword in ("우대금리", "우대조건")) and not any(keyword in text for keyword in ("문의", "확인 중", "답변")):
        return "우대금리설명부족"
    if product == "적금" and any(keyword in text for keyword in ("만기", "지급을 안", "지급 처리가", "지급을 미루")):
        return "만기지급거절"
    if product == "펀드" and any(keyword in text for keyword in ("환매", "환매금")):
        return "환매지연"
    if product == "펀드" and any(keyword in text for keyword in ("수수료", "보수", "차감", "빠져나갔")):
        return "수수료미고지"
    if product == "펀드" and any(keyword in text for keyword in ("해지 신청 방법", "절차가 너무 복잡", "절차 안내")):
        return "해지절차복잡"
    if product == "ELS" and any(keyword in text for keyword in ("조기해지", "중도 해지", "중도상환", "손실 규모")):
        return "중도해지손실"
    if product == "ELS" and any(keyword in text for keyword in ("상환금", "조기상환", "만기 정산")):
        return "상환금과소지급"
    if product == "ELS" and any(keyword in text for keyword in ("배상 비율", "배상비율", "배상 협상")):
        return "배상비율불만"
    if product == "ELS" and any(keyword in text for keyword in ("분쟁조정", "금감원")):
        return "분쟁조정안내부족"

    scored: list[tuple[int, int, str]] = []
    for order, (issue_type, keywords) in enumerate(ISSUE_RULES):
        score = sum(1 for keyword in keywords if keyword in text)
        if score:
            scored.append((score, -order, issue_type))
    if not scored:
        return "미분류"

    issue_type = max(scored)[2]
    if product == "펀드" and issue_type == "위험설명부족":
        return "위험설명부족"
    if product == "ELS" and issue_type == "위험설명부족":
        return "원금손실설명부족"
    return issue_type


def _infer_product_from_issue(issue_type: str) -> str | None:
    if issue_type in {"중도해지위약금", "자동이체누락안내", "만기지급거절", "우대금리설명부족"}:
        return "적금"
    if issue_type in {"배상비율불만", "분쟁조정안내부족", "상환금과소지급", "중도해지손실", "원금손실설명부족"}:
        return "ELS"
    return None

