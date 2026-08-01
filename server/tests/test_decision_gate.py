from __future__ import annotations

import unittest

from server.agents.decision_gate import apply_decision_gate
from server.schemas import Decision, FactResolution, IssueAnalysis


def _issue(**overrides) -> IssueAnalysis:
    data = {
        "issue_id": "issue_001",
        "product": "예금",
        "issue_type": "인출제한",
        "focal": {},
        "target": {"is_unclear": False},
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

    def test_amend_outranks_ask_per_prd_priority(self) -> None:
        # PRD 12장: hold > amend > ask > proceed. A vague complaint that both
        # exposes an account number (amend) and is missing facts (ask) must
        # resolve to amend, not silently drop the PII-confirmation step.
        decision = apply_decision_gate(
            _issue(
                missing_facts=["거래일"],
                decision=Decision(control="ask", risk_flags=["missing_facts"]),
                content_scope={"requires_user_confirmation": True, "masked_fields": ["account_number"]},
            )
        )

        self.assertEqual(decision.control, "amend")

    def test_hold_when_legal_uncertainty_is_detected(self) -> None:
        decision = apply_decision_gate(
            _issue(
                decision=Decision(control="proceed", risk_flags=["legal_uncertainty"]),
            )
        )

        self.assertEqual(decision.control, "hold")
        self.assertTrue(decision.human_review)

    def test_hold_when_suspicious_input_is_detected(self) -> None:
        decision = apply_decision_gate(
            _issue(
                decision=Decision(control="proceed", risk_flags=["suspicious_input"]),
            )
        )

        self.assertEqual(decision.control, "hold")
        self.assertTrue(decision.human_review)


if __name__ == "__main__":
    unittest.main()
