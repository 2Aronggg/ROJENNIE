from __future__ import annotations

import unittest

from agent.pipeline import PipelineResult, run_analysis
from server import app as app_module
from server.retrieval import SearchIndex


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        app_module._INDEX = SearchIndex([])
        app_module.CASE_STORE.clear()

    def test_run_analysis_connects_router_a_api_and_composer(self) -> None:
        result = run_analysis(
            "예금 계좌에서 12만원을 인출하려는데 시스템에서 계속 거부돼요. "
            "그런데 적금 우대금리 문의했는데 콜센터에서 계속 확인 중이라고만 해요, 10일째요.",
            case_id="case_pipeline",
            session_id="session_pipeline",
        )

        self.assertIsInstance(result, PipelineResult)
        self.assertEqual(result.request.case_id, "case_pipeline")
        self.assertEqual([issue.issue_id for issue in result.request.issues], ["issue_001", "issue_002"])
        self.assertEqual([(issue.product, issue.issue_type) for issue in result.analysis.issues], [("예금", "인출제한"), ("적금", "민원처리지연")])
        self.assertEqual(result.response_view.case_id, "case_pipeline")
        self.assertEqual(len(result.response_view.issues), 2)
        self.assertTrue(all(issue.status == "ask" for issue in result.response_view.issues))
        self.assertIn("case_pipeline", app_module.CASE_STORE)

    def test_pipeline_masks_pii_before_a_analysis_and_composer_marks_amend(self) -> None:
        result = run_analysis(
            "예금 계좌 123-456-789012에서 인출이 거부됐고 연락처는 010-1234-5678입니다.",
            case_id="case_masked",
        )

        issue_request = result.request.issues[0]
        issue_view = result.response_view.issues[0]

        self.assertNotIn("789012", issue_request.text)
        self.assertEqual(issue_view.status, "ask")
        self.assertEqual(issue_view.masked_fields, ["phone_number", "account_number"])
        self.assertIn("개인정보 마스킹 또는 제출 범위 확인이 필요합니다.", issue_view.decision_reasons)


if __name__ == "__main__":
    unittest.main()
