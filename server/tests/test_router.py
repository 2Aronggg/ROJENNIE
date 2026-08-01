from __future__ import annotations

import unittest
from types import SimpleNamespace

from fastapi.testclient import TestClient

from server.agents.router import (
    LLMRouteResult,
    build_case_request,
    split_prompt_to_issues,
)
from server import app as app_module
from server.rag.retrieval import SearchIndex
from server.schemas import CaseAnalyzeRequest


class _FakeModels:
    def generate_content(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(text=LLMRouteResult(
                issues=[
                    {
                        "text": "예금 통장에서 돈을 찾으려는데 출금이 거부됐어요.",
                        "product": "예금",
                        "issue_type": "인출제한",
                    },
                    {
                        "text": "ELS 조기해지 손실을 안내받지 못했어요.",
                        "product": "ELS",
                        "issue_type": "원금손실설명부족",
                    },
                ]
            ).model_dump_json())


class _FakeClient:
    def __init__(self) -> None:
        self.models = _FakeModels()


class _FailingModels:
    def generate_content(self, **kwargs):
        raise RuntimeError("test failure")


class _FailingClient:
    def __init__(self) -> None:
        self.models = _FailingModels()


class RouterTests(unittest.TestCase):
    def test_build_case_request_never_sends_empty_issues(self) -> None:
        request = build_case_request(
            "예금 계좌에서 12만원을 인출하려는데 시스템에서 계속 거부돼요.",
            case_id="case_demo",
            session_id="session_001",
            use_llm=False,
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
            "그런데 적금 우대금리 문의했는데 콜센터에서 계속 확인 중이라고만 해요, 10일째요.",
            use_llm=False,
        )

        self.assertEqual([issue.issue_id for issue in issues], ["issue_001", "issue_002"])
        self.assertEqual([(issue.product, issue.issue_type) for issue in issues], [("예금", "인출제한"), ("적금", "민원처리지연")])
        self.assertEqual(issues[0].facts[1].value, "12만원")
        self.assertEqual(issues[1].facts[1].value, "10일째")

    def test_els_and_fund_routes_are_preserved(self) -> None:
        issues = split_prompt_to_issues(
            "ELS 조기해지 시 손실 규모 12만원에 대한 설명이 부족했어요. "
            "또 펀드 환매를 신청했는데 10일째 처리가 안 되고 있어요.",
            use_llm=False,
        )

        self.assertEqual([(issue.product, issue.issue_type) for issue in issues], [("ELS", "중도해지손실"), ("펀드", "환매지연")])

    def test_llm_structured_output_is_converted_to_issue_inputs(self) -> None:
        client = _FakeClient()
        issues = split_prompt_to_issues("복합 금융 민원입니다.", use_llm=True, client=client)

        self.assertEqual([(issue.product, issue.issue_type) for issue in issues], [("예금", "인출제한"), ("ELS", "원금손실설명부족")])
        self.assertEqual(client.models.kwargs["config"]["response_mime_type"], "application/json")

    def test_llm_failure_falls_back_to_rules(self) -> None:
        issues = split_prompt_to_issues(
            "예금 계좌에서 출금이 거부됐어요.",
            use_llm=True,
            client=_FailingClient(),
        )

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].product, "예금")
        self.assertEqual(issues[0].issue_type, "인출제한")

    def test_b_payload_is_accepted_by_a_analyze_api(self) -> None:
        app_module._INDEX = SearchIndex([])
        client = TestClient(app_module.app)
        request = build_case_request(
            "예금 계좌에서 12만원을 인출하려는데 시스템에서 계속 거부돼요.",
            case_id="case_contract",
            session_id="session_contract",
            use_llm=False,
        )

        response = client.post("/api/v1/cases/analyze", json=request.model_dump(mode="json"))

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["case_id"], "case_contract")
        self.assertEqual(body["issues"][0]["product"], "예금")
        self.assertEqual(body["issues"][0]["issue_type"], "인출제한")


if __name__ == "__main__":
    unittest.main()
