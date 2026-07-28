from __future__ import annotations

import unittest

from agent.focal_builder import build_issue_input


class FocalBuilderTests(unittest.TestCase):
    def test_builds_transaction_focal_with_amount_and_unclear_target(self) -> None:
        issue = build_issue_input(
            issue_id="issue_001",
            product="예금",
            issue_type="인출제한",
            text="예금 계좌에서 12만원을 인출하려는데 시스템에서 계속 거부돼요.",
        )

        self.assertEqual(issue.focal["source"], "agent.focal_builder")
        self.assertEqual(issue.focal["type"], "transaction")
        self.assertEqual(issue.focal["amounts"], ["12만원"])
        self.assertEqual(issue.target["is_unclear"], True)
        self.assertIn("거래 금액", issue.required_facts)

    def test_extracts_institution_rate_and_product_name(self) -> None:
        issue = build_issue_input(
            issue_id="issue_001",
            product="예금",
            issue_type="금리적용오류",
            text="KB 정기예금 우대금리를 0.3% 받기로 안내받았는데 실제로는 낮게 적용됐어요.",
        )

        self.assertEqual(issue.focal["institution"], "KB")
        self.assertEqual(issue.focal["rates"], ["0.3%"])
        self.assertEqual(issue.target["action_target"], "KB 민원창구")
        self.assertTrue(any(fact.field == "product_name" for fact in issue.facts))

    def test_unsupported_product_is_kept_out_of_a_product_route(self) -> None:
        issue = build_issue_input(
            issue_id="issue_001",
            product="보험",
            issue_type="지원제외_보험",
            text="보험금 지급이 거절됐는데 사전 안내를 못 받았어요.",
            raw_product="보험",
        )

        self.assertEqual(issue.product, "공통")
        self.assertEqual(issue.focal["type"], "human_review")
        self.assertEqual(issue.focal["unsupported_product"], "보험")
        self.assertEqual(issue.target["support_status"], "unsupported")
        self.assertEqual(issue.required_facts, ["Human Review"])


if __name__ == "__main__":
    unittest.main()
