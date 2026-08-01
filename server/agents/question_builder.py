from __future__ import annotations

from typing import Any

from server.schemas import Fact


def fact_value(facts: list[Fact], field: str) -> Any:
    for fact in reversed(facts):
        if fact.field == field:
            return fact.value
    return None


def format_amount(value: Any) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value:,.0f}원"
    return str(value)


def format_rate(value: Any) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        percent = value * 100 if abs(value) <= 1 else value
        return f"연 {percent:g}%"
    text = str(value)
    return text if text.startswith("연 ") else f"연 {text}"


def expected_interest_question(facts: list[Fact]) -> str:
    details: list[str] = []
    actual = fact_value(facts, "실제 지급 금액")
    principal = fact_value(facts, "가입금액")
    rate = fact_value(facts, "실제 적용 금리")
    if actual is not None:
        details.append(f"실제 입금액은 {format_amount(actual)}")
    if principal is not None:
        details.append(f"가입금액은 {format_amount(principal)}")
    if rate is not None:
        details.append(f"적용금리는 {format_rate(rate)}")
    if details:
        return f"현재 확인된 정보는 {', '.join(details)}입니다. 얼마로 예상하셨나요?"
    return "만기 때 받을 것으로 예상하신 이자 금액은 얼마인가요?"
