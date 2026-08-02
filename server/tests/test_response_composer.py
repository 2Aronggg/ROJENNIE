from __future__ import annotations

from datetime import date
import unittest

from server.agents.response_composer import compose_case_response
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
                    target={},
                    facts=[Fact(field="amount", value="12만원", source_ref="user_input")],
                    missing_facts=["거래일", "금융회사명", "거부 사유 안내", "추가 질문"],
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
                    target={},
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

    def test_hold_for_identity_theft(self) -> None:
        case = CaseAnalysis(
            case_id="case_hold",
            prompt="명의도용",
            issues=[
                IssueAnalysis(
                    issue_id="issue_002",
                    product="예금",
                    issue_type="명의도용",
                    focal={"type": "identity_or_auth_record"},
                    target={},
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

        self.assertEqual([issue.status for issue in view.issues], ["hold"])
        self.assertTrue(all(issue.human_review for issue in view.issues))

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
                    target={"is_unclear": False},
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

    def test_closing_dedupes_documents_for_shared_contract(self) -> None:
        shared_facts = [
            Fact(field="상품명", value="2025 정기예금", source_ref="user_input"),
            Fact(field="가입일", value="2025-03-10", source_ref="user_input"),
        ]
        case = CaseAnalysis(
            case_id="case_shared_contract",
            prompt="같은 예금 계약에서 우대금리와 중도해지 수수료가 문제입니다.",
            issues=[
                IssueAnalysis(
                    issue_id="issue_001",
                    product="예금",
                    issue_type="우대금리설명부족",
                    focal={"type": "notice", "product_name": "2025 정기예금", "contract_date": "2025-03-10"},
                    target={},
                    facts=shared_facts,
                    missing_facts=[],
                    fact_resolution=FactResolution(),
                    evidence_refs=[],
                    decision=Decision(control="proceed", risk_flags=[]),
                    next_steps=[],
                ),
                IssueAnalysis(
                    issue_id="issue_002",
                    product="예금",
                    issue_type="중도해지위약금",
                    focal={"type": "contract", "product_name": "2025 정기예금", "contract_date": "2025-03-10"},
                    target={},
                    facts=shared_facts,
                    missing_facts=[],
                    fact_resolution=FactResolution(),
                    evidence_refs=[],
                    decision=Decision(control="proceed", risk_flags=[]),
                    next_steps=[],
                ),
            ],
        )

        view = compose_case_response(case)

        self.assertEqual(len(view.closing["documents"]), 1)
        self.assertIn("2025-03-10", view.closing["documents"][0])
        self.assertEqual(view.closing["documents"][0].count("상품설명서"), 1)
        self.assertIn("해지 신청 내역", view.closing["documents"][0])
        self.assertIn("수수료 산정 내역", view.closing["documents"][0])

    def test_missing_questions_use_specific_natural_language_templates(self) -> None:
        case = CaseAnalysis(
            case_id="case_missing_templates",
            prompt="중도해지 수수료 설명이 부족했습니다.",
            issues=[
                IssueAnalysis(
                    issue_id="issue_001",
                    product="예금",
                    issue_type="중도해지위약금",
                    focal={"type": "contract"},
                    target={},
                    facts=[],
                    missing_facts=["설명서 수령 여부", "위약금 또는 수수료 금액"],
                    fact_resolution=FactResolution(),
                    evidence_refs=[],
                    decision=Decision(control="ask", risk_flags=["missing_facts"]),
                    next_steps=[],
                )
            ],
        )

        view = compose_case_response(case)
        questions = view.issues[0].missing_questions

        self.assertEqual(questions[0].question, "상품설명서를 받았거나 확인했다는 기록이 있나요?")
        self.assertEqual(questions[1].question, "차감된 위약금이나 수수료 금액을 알려주세요.")
        self.assertFalse(any("을(를)" in item.question for item in questions))
        self.assertTrue(all(item.reason != "검색 근거와 사실관계를 같은 민원에 연결하기 위해 필요합니다." for item in questions))

if __name__ == "__main__":
    unittest.main()
