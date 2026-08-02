from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from server.agents.report_composer import compose_issue_report
from server.schemas import Decision, EvidenceRef, Fact, FactResolution, IssueAnalysis


class ReportComposerTests(unittest.TestCase):
    def test_forbidden_report_claims_trigger_fallback(self) -> None:
        issue = IssueAnalysis(
            issue_id="issue_001",
            product="예금",
            issue_type="인출제한",
            focal={"type": "transaction"},
            target={},
            facts=[Fact(field="user_statement", value="계좌에서 돈이 안 나갔어요.")],
            missing_facts=["거래일"],
            fact_resolution=FactResolution(),
            evidence_refs=[
                EvidenceRef(
                    doc_id="doc_001",
                    chunk_id="chunk_001",
                    path="local:regulations/은행법.pdf",
                    page=12,
                    section="제18조",
                    score=0.42,
                    snippet="근거 문서 일부",
                )
            ],
            decision=Decision(control="ask", risk_flags=[]),
            next_steps=["거래일을 확인하세요."],
        )

        with patch(
            "server.agents.report_composer.LLMPolicyGateway.generate_json",
            return_value=SimpleNamespace(
                text='{"complaint_content":"민원 내용","issue":"인출제한","processing_result":"배상액 100만원을 지급해야 합니다","consumer_cautions":["배상액을 요구"],"used_evidence_chunk_ids":["chunk_001"],"reasoning":"법적 결론에 해당합니다","follow_up_actions":["외부 제출"]}'
            ),
        ):
            report = compose_issue_report(issue, use_llm=True)

        self.assertEqual(report.generated_by, "fallback")
        self.assertTrue(report.compliance_blocked)
        self.assertIn("llm_output_forbidden_claim", report.compliance_flags)
        self.assertEqual(report.current_decision, "추가 확인 필요")
        self.assertNotIn("배상액", report.processing_result)
        self.assertNotIn("법적 결론", report.processing_result)
        self.assertNotIn("외부 제출", report.processing_result)
        self.assertEqual(report.follow_up_actions, ["거래일을 확인하세요."])


if __name__ == "__main__":
    unittest.main()
