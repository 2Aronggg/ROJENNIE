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

    def test_emotional_preamble_does_not_become_its_own_unclassified_issue(self) -> None:
        # "아니 진짜 너무 화나서 미치겠는데요!!!"처럼 상품/쟁점 신호가 전혀 없는
        # 서두는 첫 조각이라는 이유만으로 신호 검사를 건너뛰고 무조건 하나의
        # span으로 굳어진다. 뒤에 실제 신호("예금 이자를...")가 오면 그 경계에서
        # 분리돼 감정 표현만 있는 "공통/미분류" 카드가 실제 민원과 별도로 뜨던
        # 문제 - 하나의 이슈로 합쳐져야 한다.
        issues = split_prompt_to_issues(
            "아니 진짜 너무 화나서 미치겠는데요!!! 은행이 대체 왜 이러는지 모르겠어요 "
            "저 지금 완전 스트레스받아서 죽을것같은데 예금 이자를 왜 이렇게 적게 주는거예요??? "
            "말이 되나요 진짜???",
            use_llm=False,
        )

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].product, "예금")
        self.assertIn("예금 이자", issues[0].text)

    def test_second_clause_inherits_product_from_prior_clause_when_unstated(self) -> None:
        # "정기예금에 가입했는데... 그리고 중도해지 수수료가..."처럼 두 번째 절이
        # 상품명을 생략하면, 예전에는 issue_type만 보고 하드코딩된 매핑
        # (중도해지위약금 -> 적금)으로 잘못 넘어갔다. 직전 절에서 확인된 "예금"을
        # 이어받아야 한다.
        issues = split_prompt_to_issues(
            "KB 정기예금에 작년 3월 10일 1년 만기로 가입했습니다. 만기 후 이자를 확인해보니, "
            "가입 당시 안내받았던 우대금리 3.5%가 아니라 기본금리 2.1%로만 이자가 계산되어 있었습니다. "
            "그리고 이 건과 별개로 지금 급하게 돈이 필요해 중도해지를 하려는데, "
            "가입할 때 안내받은 중도해지 수수료율과 현재 창구에서 안내받은 수수료율이 다릅니다.",
            use_llm=False,
        )

        self.assertGreaterEqual(len(issues), 2)
        self.assertEqual(issues[0].product, "예금")
        last_issue = issues[-1]
        self.assertEqual(last_issue.issue_type, "중도해지위약금")
        self.assertEqual(last_issue.product, "예금")

    def test_multi_product_keyword_conflict_picks_the_stronger_match(self) -> None:
        # "예금"은 한 번, "대출"도 한 번 나오면 기존 우선순위(대출이 앞순위)를 따르는
        # 게 맞지만, 한쪽 키워드가 여러 번 반복되면 그쪽이 더 강한 신호다.
        issues = split_prompt_to_issues(
            "정기예금 계좌 정기예금 상품 예금 통장에서 대출 상환하려는데 위약금이 이상해요",
            use_llm=False,
        )

        self.assertEqual(issues[0].product, "예금")

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
