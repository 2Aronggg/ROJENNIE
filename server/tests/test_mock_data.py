from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server import app as app_module
from server.agents.facts import missing_facts, resolve_facts
from server.agents.mock_customer_data_resolver import MockCustomerDataResolver
from server.agents.pipeline import run_analysis
from server.agents.router import build_case_request
from server.finance.mock_data import MockBankClient
from server.rag.retrieval import SearchIndex


class MockDataTests(unittest.TestCase):
    def test_resolver_reads_sqlite_customer_and_accounts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            resolver = MockCustomerDataResolver(MockBankClient(Path(directory) / "mock.sqlite3"))
            context = resolver.resolve("CUST-001")

        self.assertIsNotNone(context)
        self.assertEqual(context["customer"]["consent_status"], "granted")
        self.assertEqual(context["accounts"][0]["account_id"], "DEP-001")
        self.assertEqual(context["accounts"][0]["net_interest"], 279180)

    def test_mock_read_apis(self) -> None:
        client = TestClient(app_module.app)

        products = client.get("/mock/customers/CUST-001/products")
        self.assertEqual(products.status_code, 200)
        self.assertEqual(products.json()["deposits"][0]["account_id"], "DEP-001")
        self.assertEqual(products.json()["savings"][0]["account_id"], "SAV-001")

        deposits = client.get("/mock/customers/CUST-001/deposits")
        self.assertEqual(deposits.json()[0]["net_interest"], 279180)
        self.assertEqual(client.get("/mock/accounts/SAV-001/rate-history").json(), [])
        self.assertEqual(client.get("/mock/accounts/SAV-001/notice-history").json(), [])
        self.assertEqual(client.get("/mock/accounts/DEP-001/transactions").json()[0]["amount"], 279180)

        loans = client.get("/mock/customers/CUST-001/loans")
        self.assertEqual(loans.status_code, 200)
        self.assertEqual(loans.json()[0]["account_id"], "LOAN-001")
        self.assertEqual(loans.json()[0]["product_name"], "KB 직장인든든 신용대출")
        self.assertEqual(loans.json()[0]["executed_at"], "2025-03-15")
        self.assertEqual(loans.json()[0]["rate_index"], "MOR 6개월")
        self.assertEqual(loans.json()[0]["outstanding_balance"], 24_180_000)
        self.assertEqual(client.get("/mock/accounts/LOAN-001/repayments").json()[0]["amount"], 565_000)
        self.assertEqual(client.get("/mock/accounts/LOAN-001/notice-history").json(), [])

    def test_resolver_facts_carry_event_and_recorded_dates(self) -> None:
        # opened_at/maturity_at 등 필드값 자체가 날짜인 사실은 event_date로도 남아야
        # resolve_facts()의 최신값 비교가 date.min끼리의 우연한 순서가 아니라 실제
        # 시점 비교가 된다.
        with tempfile.TemporaryDirectory() as directory:
            resolver = MockCustomerDataResolver(MockBankClient(Path(directory) / "mock.sqlite3"))
            context = resolver.resolve("CUST-001")

        issue = build_case_request("정기예금 만기 이자가 예상과 다릅니다.", use_llm=False).issues[0]
        facts = resolver.facts_for_issue(issue, context)

        joined_date = next(fact for fact in facts if fact.field == "가입일")
        self.assertEqual(str(joined_date.event_date), joined_date.value)
        self.assertIsNotNone(joined_date.recorded_date)

        rate_fact = next(fact for fact in facts if fact.field == "실제 적용 금리")
        self.assertIsNone(rate_fact.event_date)
        self.assertIsNotNone(rate_fact.recorded_date)

    def test_loan_is_resolved_into_case_facts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            resolver = MockCustomerDataResolver(MockBankClient(Path(directory) / "mock.sqlite3"))
            context = resolver.resolve("CUST-001")

        loan = next(account for account in context["accounts"] if account["account_id"] == "LOAN-001")
        request = build_case_request("대출 금리 변경 안내를 받지 못했습니다.", use_llm=False)
        issue = request.issues[0]
        facts = resolver.facts_for_issue(issue, context)

        self.assertEqual(issue.product, "대출")
        self.assertEqual(issue.issue_type, "대출금리변경미통지")
        self.assertEqual(loan["product_type"], "loan")
        self.assertEqual(next(fact.value for fact in facts if fact.field == "현재잔액"), 24_180_000)
        self.assertEqual(next(fact.value for fact in facts if fact.field == "상환방식"), "원리금균등상환")
        self.assertEqual(next(fact.value for fact in facts if fact.field == "금리 기준"), "MOR 6개월")
        self.assertEqual(next(fact.value for fact in facts if fact.field == "안내 수신 여부"), False)
        # 변경 전 금리는 이력에만 있으므로 별도 사실로 풀려야 재질문이 생기지 않는다.
        self.assertEqual(next(fact.value for fact in facts if fact.field == "기존 금리"), 0.047)
        self.assertNotIn("기존 금리", missing_facts(issue.required_facts, resolve_facts(facts)))

    def test_demo_prompt_uses_mock_facts_and_expected_decisions(self) -> None:
        app_module._INDEX = SearchIndex.from_data_dir(
            app_module.DATA_DIR,
            chunks_path=app_module.CHUNKS_PATH,
        )
        result = run_analysis(
            "예금 만기 이자 금액이 예상과 다르고, 적금 금리 변경 안내도 받지 못했습니다.",
            case_id="case_mock_demo",
            use_llm=False,
        )

        self.assertEqual([issue.issue_type for issue in result.analysis.issues], ["거래오류", "금리변경미통지"])
        self.assertEqual([issue.decision.control for issue in result.analysis.issues], ["ask", "proceed"])
        self.assertIn("안내 금액", result.analysis.issues[0].missing_facts)
        expected_question = "현재 확인된 정보는 실제 입금액은 279,180원, 가입금액은 10,000,000원, 적용금리는 연 3.3%입니다. 얼마로 예상하셨나요?"
        self.assertIn(expected_question, result.analysis.issues[0].next_steps)
        self.assertEqual(result.response_view.issues[0].missing_questions[0].question, expected_question)
        self.assertEqual(
            next(fact.value for fact in result.analysis.issues[0].facts if fact.field == "실제 지급 금액"),
            279180,
        )
        self.assertEqual(result.analysis.issues[1].mock_data["account"]["rate_change_history"], [])

    def test_missing_expected_amount_uses_mcp_facts_first(self) -> None:
        app_module._INDEX = SearchIndex.from_data_dir(
            app_module.DATA_DIR,
            chunks_path=app_module.CHUNKS_PATH,
        )
        result = run_analysis(
            "예금 만기 이자 금액이 예상과 다릅니다.",
            case_id="case_known_facts_first",
            use_llm=False,
        )

        issue = result.analysis.issues[0]
        self.assertIn("안내 금액", issue.missing_facts)
        self.assertIn("실제 지급 금액", {fact.field for fact in issue.facts})
        self.assertIn("가입금액", {fact.field for fact in issue.facts})
        self.assertIn("실제 적용 금리", {fact.field for fact in issue.facts})
        self.assertIn("실제 입금액은 279,180원", issue.next_steps[0])
        self.assertNotIn("실제로 입금된 세후 이자는 얼마였나요?", issue.next_steps[0])


if __name__ == "__main__":
    unittest.main()
