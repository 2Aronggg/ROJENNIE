from __future__ import annotations

import unittest

from agent.decision_gate import apply_decision_gate
from server.schemas import Decision, FactResolution, IssueAnalysis


def _issue(**overrides) -> IssueAnalysis:
    data = {
        "issue_id": "issue_001",
        "product": "예금",
        "issue_type": "인출제한",
        "focal": {},
        "target": {"support_status": "supported", "is_unclear": False},
        "facts": [],
        "missing_facts": [],
        "fact_resolution": FactResolution(),
        "evidence_refs": [],
        "decision": Decision(control="proceed", risk_flags=[]),
        "content_scope": {},
        "next_steps": [],
    }
    data.update(overrides)
    return IssueAnalysis(**data)


class DecisionGateTests(unittest.TestCase):
    def test_hold_has_priority_over_ask_and_amend(self) -> None:
        decision = apply_decision_gate(
            _issue(
                issue_type="명의도용",
                missing_facts=["인증 기록"],
                decision=Decision(control="ask", risk_flags=["missing_facts"]),
                content_scope={"requires_user_confirmation": True},
            )
        )

        self.assertEqual(decision.control, "hold")
        self.assertTrue(decision.human_review)

    def test_missing_facts_upgrade_proceed_to_ask(self) -> None:
        decision = apply_decision_gate(_issue(missing_facts=["거래일"], decision=Decision(control="proceed", risk_flags=[])))

        self.assertEqual(decision.control, "ask")
        self.assertIn("핵심 사실이 부족합니다.", decision.reasons)

    def test_masking_requires_amend_when_no_higher_risk_exists(self) -> None:
        decision = apply_decision_gate(
            _issue(
                decision=Decision(control="proceed", risk_flags=[]),
                content_scope={"requires_user_confirmation": True, "masked_fields": ["account_number"]},
            )
        )

        self.assertEqual(decision.control, "amend")

    def test_unsupported_product_goes_to_hold(self) -> None:
        decision = apply_decision_gate(
            _issue(
                product="공통",
                issue_type="지원제외_보험",
                target={"support_status": "unsupported"},
                decision=Decision(control="ask", risk_flags=["evidence_insufficient"]),
            )
        )

        self.assertEqual(decision.control, "hold")
        self.assertTrue(decision.human_review)


if __name__ == "__main__":
    unittest.main()
