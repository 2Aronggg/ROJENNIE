from __future__ import annotations

from datetime import date, datetime
from typing import Any

from server.schemas import Fact, IssueInput


DEFAULT_CUSTOMER_ID = "CUST-001"


def _parse_date(value: Any) -> date | None:
    """Best-effort ISO date parse for mock-ledger fields like "2025-08-01".

    Returns None for anything else (rates, amounts, lists) rather than raising -
    those fields simply have no event_date, which is honest: we don't know when
    that value's underlying event happened, only that we looked it up now.
    """
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


class MockCustomerDataResolver:
    """Resolve the demo customer context through bank-like read methods."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def resolve(self, customer_id: str | None = None) -> dict[str, Any] | None:
        customer_id = customer_id or DEFAULT_CUSTOMER_ID
        customer = self.client.get_customer(customer_id)
        if customer is None:
            return None

        access_granted = customer.get("authenticated") is True and customer.get("consent_status") == "granted"
        if not access_granted:
            return {
                "customer": customer,
                "products": {"deposits": [], "savings": [], "loans": []},
                "accounts": [],
                "access_granted": False,
                "source_apis": [],
            }
        products = self.client.get_products(customer_id)
        accounts = [
            *(self.client.get_deposits(customer_id)),
            *(self.client.get_savings(customer_id)),
            *(self.client.get_loans(customer_id)),
        ]
        for account in accounts:
            account["transactions"] = self.client.get_transactions(account["account_id"])
            if account["product_type"] == "loan":
                account["repayments"] = self.client.get_repayments(account["account_id"])
        source = self.client.source_ref if hasattr(self.client, "source_ref") else lambda tool: f"/mock/{tool}"
        return {
            "customer": customer,
            "products": products,
            "access_granted": True,
            "accounts": accounts,
            "source_apis": [
                source("get_my_profile"),
                source("get_my_products"),
                source("get_my_deposits"),
                source("get_my_savings"),
                source("get_my_loans"),
            ],
        }

    def facts_for_issue(self, issue: IssueInput, context: dict[str, Any] | None) -> list[Fact]:
        if not context:
            return []
        account = self._account_for_issue(issue, context["accounts"])
        if not account:
            return []

        account_id = account["account_id"]
        account_ref = self.client.source_ref("get_my_account") if hasattr(self.client, "source_ref") else f"/mock/accounts/{account_id}"
        facts = [
            self._fact("customer_id", context["customer"]["customer_id"], self.client.source_ref("get_my_profile") if hasattr(self.client, "source_ref") else "/mock/customers"),
            self._fact("account_id", account_id, account_ref),
            self._fact("상품명", account["product_name"], account_ref),
            self._fact("가입일", account["opened_at"], account_ref, event_date=_parse_date(account["opened_at"])),
            self._fact("만기일", account["maturity_at"], account_ref, event_date=_parse_date(account["maturity_at"])),
            self._fact("기본금리", account.get("base_rate"), account_ref),
            self._fact("우대금리", account.get("preferential_rate"), account_ref),
            self._fact("실제 적용 금리", account.get("applied_rate"), account_ref),
            self._fact("기존 금리", self._previous_rate(account), f"{account_ref}/rate-history"),
        ]
        if account["product_type"] == "deposit":
            facts.extend(
                [
                    self._fact("거래일", account["maturity_at"], account_ref, event_date=_parse_date(account["maturity_at"])),
                    self._fact("실제 지급 금액", account["net_interest"], account_ref),
                    self._fact("세전 이자", account["gross_interest"], account_ref),
                    self._fact("세금", account["tax"], account_ref),
                    self._fact("가입금액", account["principal"], account_ref),
                ]
            )
        elif account["product_type"] == "installment_savings":
            conditions = account.get("preferential_conditions", [])
            failed_condition = next((item for item in conditions if item.get("status") == "failed"), None)
            facts.extend(
                [
                    self._fact("우대금리 조건", conditions, account_ref),
                    self._fact("우대조건 상태", failed_condition.get("status") if failed_condition else "충족", account_ref),
                    self._fact(
                        "자동이체 실패일",
                        failed_condition.get("failed_at") if failed_condition else None,
                        account_ref,
                        event_date=_parse_date(failed_condition.get("failed_at")) if failed_condition else None,
                    ),
                    self._fact("금리 변경 이력", account.get("rate_change_history", []), f"{account_ref}/rate-history"),
                    self._fact("안내 이력", account.get("notice_history", []), f"{account_ref}/notice-history"),
                    self._fact("안내 수신 여부", bool(account.get("notice_history")), f"{account_ref}/notice-history"),
                ]
            )
        else:
            facts.extend(
                [
                    self._fact("대출원금", account.get("principal"), account_ref),
                    self._fact(
                        "대출 실행일",
                        account.get("executed_at", account.get("opened_at")),
                        account_ref,
                        event_date=_parse_date(account.get("executed_at", account.get("opened_at"))),
                    ),
                    self._fact("현재잔액", account.get("outstanding_balance"), account_ref),
                    self._fact("금리유형", account.get("rate_type"), account_ref),
                    self._fact("금리 기준", account.get("rate_index"), account_ref),
                    self._fact("금리 재산정 주기", account.get("rate_reset_cycle_months"), account_ref),
                    self._fact(
                        "다음 금리 재산정일",
                        account.get("next_rate_reset_at"),
                        account_ref,
                        event_date=_parse_date(account.get("next_rate_reset_at")),
                    ),
                    self._fact("상환방식", account.get("repayment_method"), account_ref),
                    self._fact("월상환액", account.get("monthly_payment"), account_ref),
                    self._fact(
                        "최근 상환일",
                        account.get("last_payment_at"),
                        account_ref,
                        event_date=_parse_date(account.get("last_payment_at")),
                    ),
                    self._fact(
                        "다음 상환일",
                        account.get("next_payment_at"),
                        account_ref,
                        event_date=_parse_date(account.get("next_payment_at")),
                    ),
                    self._fact("중도상환수수료율", account.get("early_repayment_fee_rate"), account_ref),
                    self._fact("연체 여부", account.get("delinquency_status"), account_ref),
                    self._fact("상환 내역", account.get("repayments", []), f"{account_ref}/repayments"),
                    self._fact("금리 변경 이력", account.get("rate_change_history", []), f"{account_ref}/rate-history"),
                    self._fact("안내 이력", account.get("notice_history", []), f"{account_ref}/notice-history"),
                    self._fact("안내 수신 여부", bool(account.get("notice_history")), f"{account_ref}/notice-history"),
                ]
            )
        return [fact for fact in facts if fact.value is not None]

    @staticmethod
    def _account_for_issue(issue: IssueInput, accounts: list[dict[str, Any]]) -> dict[str, Any] | None:
        product_type = {"예금": "deposit", "적금": "installment_savings", "대출": "loan"}.get(issue.product)
        return next((account for account in accounts if account["product_type"] == product_type), None)

    @staticmethod
    def _previous_rate(account: dict[str, Any]) -> Any:
        """금리 변경 전 금리는 이력에만 있어 그대로 두면 미확인 사실로 남는다."""
        history = account.get("rate_change_history") or []
        latest = max(history, key=lambda item: str(item.get("changed_at", "")), default=None)
        return latest.get("previous_rate") if latest else None

    @staticmethod
    def _fact(field: str, value: Any, source_ref: str, *, event_date: date | None = None) -> Fact:
        # recorded_date=오늘: 이 Fact를 "지금 이 조회로 확인했다"는 시점. event_date는
        # 그 값이 가리키는 사건 자체의 날짜(가입일이면 가입일 그 값)로, 필드값 자체가
        # 날짜인 경우에만 넘겨준다. 없으면 resolve_facts()의 최신값 비교가 date.min끼리
        # 비교돼 사실상 무작위 순서에 의존하게 된다.
        # Finance MCP/mock 원장에서 읽은 값은 사용자 발언이 아니라 시스템이 조회해
        # 확인한 사실이다. source_type 기본값(USER_STATED)을 그대로 두면 이 값이
        # verified_facts와 user_statements를 구분하는 규칙(00_SHARED_RULES 1번)을
        # 스키마 레벨에서 어기게 된다.
        return Fact(
            field=field,
            value=value,
            source_type="SYSTEM_INFERRED",
            source_ref=source_ref,
            confidence=1.0,
            event_date=event_date,
            recorded_date=date.today(),
        )
