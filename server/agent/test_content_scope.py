from __future__ import annotations

import unittest

from server.agent.content_scope import apply_content_scope
from server.agent.decision_gate import apply_decision_gate
from server.agent.focal_builder import build_issue_input
from server.schemas import Decision, FactResolution, IssueAnalysis


class ContentScopeTests(unittest.TestCase):
    def test_masks_resident_phone_account_card_and_auth_code(self) -> None:
        result = apply_content_scope(
            "주민번호 900101-1234567, 전화 010-1234-5678, 계좌 123-456-789012, "
            "카드 1111-2222-3333-4444, 인증번호 123456입니다."
        )

        self.assertIn("900101-*******", result.text)
        self.assertIn("010-****-5678", result.text)
        self.assertIn("123-***-****12", result.text)
        self.assertIn("1111-****-****-4444", result.text)
        self.assertIn("인증번호 ******", result.text)
        self.assertEqual(
            result.masked_fields,
            [
                "resident_registration_number",
                "phone_number",
                "card_number",
                "account_number",
                "auth_or_password",
            ],
        )
        self.assertTrue(result.requires_user_confirmation)

    def test_focal_builder_sends_masked_text_to_a_contract(self) -> None:
        issue = build_issue_input(
            issue_id="issue_001",
            product="예금",
            issue_type="인출제한",
            text="예금 계좌 123-456-789012에서 12만원 인출이 거부됐고 연락처는 010-1234-5678입니다.",
        )

        self.assertNotIn("789012", issue.text)
        self.assertIn("account_number", issue.focal["content_scope"]["masked_fields"])
        self.assertIn("phone_number", issue.focal["content_scope"]["masked_fields"])
        self.assertTrue(issue.focal["content_scope"]["requires_user_confirmation"])

    def test_decision_gate_amends_when_focal_scope_requires_confirmation(self) -> None:
        issue_input = build_issue_input(
            issue_id="issue_001",
            product="예금",
            issue_type="인출제한",
            text="예금 계좌 123-456-789012에서 인출이 거부됐어요.",
        )
        analysis = IssueAnalysis(
            issue_id=issue_input.issue_id,
            product=issue_input.product,
            issue_type=issue_input.issue_type,
            focal=issue_input.focal,
            target={"support_status": "supported", "is_unclear": False},
            facts=issue_input.facts,
            missing_facts=[],
            fact_resolution=FactResolution(),
            evidence_refs=[],
            decision=Decision(control="proceed", risk_flags=[]),
            content_scope={},
            next_steps=[],
        )

        decision = apply_decision_gate(analysis)

        self.assertEqual(decision.control, "amend")
        self.assertIn("개인정보 마스킹 또는 제출 범위 확인이 필요합니다.", decision.reasons)


if __name__ == "__main__":
    unittest.main()
