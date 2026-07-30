from __future__ import annotations

from datetime import date
import unittest

from agent.response_composer import compose_case_response
from server.schemas import CaseAnalysis, Decision, EvidenceRef, Fact, FactResolution, IssueAnalysis


class ResponseComposerTests(unittest.TestCase):
    def test_compose_keeps_questions_and_evidence_per_issue(self) -> None:
        case = CaseAnalysis(
            case_id="case_demo",
            session_id="session_001",
            prompt="복합 민원",
            issues=[
                IssueAnalysis(
                    issue_id="issue_001",
                    product="예금",
                    issue_type="인출제한",
                    focal={"type": "transaction"},
                    target={"support_status": "supported"},
                    facts=[Fact(field="amount", value="12만원", source_ref="user_input")],
                    missing_facts=["거래일", "금융회사명", "거부 사유 안내", "추가 질문"],
                    fact_resolution=FactResolution(),
                    evidence_refs=[
                        EvidenceRef(
                            doc_id="doc_001",
                            chunk_id="chunk_001",
                            path="local:공통규정/은행법.pdf",
                            page=12,
                            section="제18조",
                            score=0.42,
                            snippet="근거 문서 일부",
                            effective_from=date(2026, 1, 2),
                        )
                    ],
                    decision=Decision(control="ask", risk_flags=["missing_facts"]),
                    next_steps=["거래일과 금융회사명을 확인하세요."],
                ),
                IssueAnalysis(
                    issue_id="issue_002",
                    product="펀드",
                    issue_type="환매지연",
                    focal={"type": "transaction"},
                    target={"support_status": "supported"},
                    facts=[],
                    missing_facts=["환매 신청일"],
                    fact_resolution=FactResolution(),
                    evidence_refs=[],
                    decision=Decision(control="ask", risk_flags=["missing_facts", "evidence_insufficient"]),
                    next_steps=["환매 신청 내역을 추가하세요."],
                ),
            ],
        )

        view = compose_case_response(case)

        self.assertEqual(view.case_id, "case_demo")
        self.assertEqual(len(view.issues), 2)
        self.assertEqual(view.issues[0].missing_questions[0].field, "거래일")
        self.assertEqual(len(view.issues[0].missing_questions), 3)
        self.assertEqual(view.issues[0].evidence[0].title, "은행법.pdf")
        self.assertEqual(view.issues[1].evidence, [])
        self.assertTrue(all(item.startswith("issue_") for item in view.closing["now"]))

    def test_hold_for_unsupported_or_identity_theft(self) -> None:
        case = CaseAnalysis(
            case_id="case_hold",
            prompt="대출 또는 명의도용",
            issues=[
                IssueAnalysis(
                    issue_id="issue_001",
                    product="공통",
                    issue_type="지원제외_대출",
                    focal={"type": "human_review"},
                    target={"support_status": "unsupported"},
                    facts=[],
                    missing_facts=[],
                    fact_resolution=FactResolution(),
                    evidence_refs=[],
                    decision=Decision(control="ask", risk_flags=["evidence_insufficient"]),
                    next_steps=[],
                ),
                IssueAnalysis(
                    issue_id="issue_002",
                    product="예금",
                    issue_type="명의도용",
                    focal={"type": "identity_or_auth_record"},
                    target={"support_status": "supported"},
                    facts=[],
                    missing_facts=["인증 기록"],
                    fact_resolution=FactResolution(),
                    evidence_refs=[],
                    decision=Decision(control="ask", risk_flags=["missing_facts"]),
                    next_steps=[],
                ),
            ],
        )

        view = compose_case_response(case)

        self.assertEqual([issue.status for issue in view.issues], ["hold", "hold"])
        self.assertTrue(all(issue.human_review for issue in view.issues))
        self.assertIn("Human Review", view.issues[0].status_description)

    def test_composer_exposes_masked_fields_from_focal_scope(self) -> None:
        case = CaseAnalysis(
            case_id="case_masking",
            prompt="계좌번호 포함",
            issues=[
                IssueAnalysis(
                    issue_id="issue_001",
                    product="예금",
                    issue_type="인출제한",
                    focal={"type": "transaction", "content_scope": {"masked_fields": ["account_number"], "requires_user_confirmation": True}},
                    target={"support_status": "supported", "is_unclear": False},
                    facts=[],
                    missing_facts=[],
                    fact_resolution=FactResolution(),
                    evidence_refs=[],
                    decision=Decision(control="proceed", risk_flags=[]),
                    content_scope={},
                    next_steps=[],
                )
            ],
        )

        view = compose_case_response(case)

        self.assertEqual(view.issues[0].status, "amend")
        self.assertEqual(view.issues[0].masked_fields, ["account_number"])

if __name__ == "__main__":
    unittest.main()
