from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from agent.router import build_case_request, split_prompt_to_issues
from server import app as app_module
from server.retrieval import SearchIndex
from server.schemas import CaseAnalyzeRequest


class RouterTests(unittest.TestCase):
    def test_build_case_request_never_sends_empty_issues(self) -> None:
        request = build_case_request(
            "예금 계좌에서 12만원을 인출하려는데 시스템에서 계속 거부돼요.",
            case_id="case_demo",
            session_id="session_001",
        )

        self.assertIsInstance(request, CaseAnalyzeRequest)
        self.assertEqual(request.case_id, "case_demo")
        self.assertEqual(len(request.issues), 1)
        self.assertEqual(request.issues[0].product, "예금")
        self.assertEqual(request.issues[0].issue_type, "인출제한")
        self.assertIn("거래 금액", request.issues[0].required_facts)

    def test_complex_prompt_is_split_into_a_api_issue_inputs(self) -> None:
        issues = split_prompt_to_issues(
            "예금 계좌에서 12만원을 인출하려는데 시스템에서 계속 거부돼요. "
            "그런데 적금 우대금리 문의했는데 콜센터에서 계속 확인 중이라고만 해요, 10일째요."
        )

        self.assertEqual([issue.issue_id for issue in issues], ["issue_001", "issue_002"])
        self.assertEqual([(issue.product, issue.issue_type) for issue in issues], [("예금", "인출제한"), ("적금", "민원처리지연")])
        self.assertEqual(issues[0].facts[1].value, "12만원")
        self.assertEqual(issues[1].facts[1].value, "10일째")

    def test_els_and_fund_routes_are_preserved(self) -> None:
        issues = split_prompt_to_issues(
            "ELS 조기해지 시 손실 규모 12만원에 대한 설명이 부족했어요. "
            "또 펀드 환매를 신청했는데 10일째 처리가 안 되고 있어요."
        )

        self.assertEqual([(issue.product, issue.issue_type) for issue in issues], [("ELS", "중도해지손실"), ("펀드", "환매지연")])

    def test_b_payload_is_accepted_by_a_analyze_api(self) -> None:
        app_module._INDEX = SearchIndex([])
        client = TestClient(app_module.app)
        request = build_case_request(
            "예금 계좌에서 12만원을 인출하려는데 시스템에서 계속 거부돼요.",
            case_id="case_contract",
            session_id="session_contract",
        )

        response = client.post("/api/v1/cases/analyze", json=request.model_dump(mode="json"))

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["case_id"], "case_contract")
        self.assertEqual(body["issues"][0]["product"], "예금")
        self.assertEqual(body["issues"][0]["issue_type"], "인출제한")


if __name__ == "__main__":
    unittest.main()
