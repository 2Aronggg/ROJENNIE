from __future__ import annotations

import unittest
from datetime import datetime

from server.agents.decision_gate import apply_decision_gate
from server.agents.issue_validator import IssueValidator
from server.schemas import CaseAnalyzeRequest, Decision, EvidenceRef, Fact, FactResolution, IssueAnalysis, IssueInput


class DecisionAuditTests(unittest.TestCase):
    """Test 3. 결정 감사 로그와 false negative 방어"""
    
    def test_audit_log_created_for_every_decision(self) -> None:
        """모든 결정마다 감사 로그가 생성되는지 확인"""
        issue = IssueAnalysis(
            issue_id="issue_001",
            product="예금",
            issue_type="인출제한",
            focal={"type": "transaction"},
            target={},
            facts=[Fact(field="amount", value="100만원")],
            missing_facts=[],
            fact_resolution=FactResolution(),
            evidence_refs=[],
            decision=Decision(control="ask", risk_flags=[]),
            next_steps=[],
        )
        
        gate = apply_decision_gate(issue)
        
        # 감사 로그가 생성됐는지 확인
        self.assertIsNotNone(gate.audit_log)
        self.assertEqual(gate.audit_log.issue_id, "issue_001")
        self.assertIsNotNone(gate.audit_log.audit_id)
        self.assertIsNotNone(gate.audit_log.created_at)
        self.assertEqual(gate.audit_log.event_type, "decision_gate")
    
    def test_false_negative_risk_high_for_risky_proceed(self) -> None:
        """고위험 신호가 있는데 proceed가 나오면 false negative risk가 높아야 함"""
        issue = IssueAnalysis(
            issue_id="issue_001",
            product="예금",
            issue_type="명의도용",  # HIGH_RISK
            focal={"type": "identity_or_auth_record"},
            target={},
            facts=[],
            missing_facts=["인증 기록", "금융회사 답변"],
            fact_resolution=FactResolution(),
            evidence_refs=[],
            decision=Decision(control="proceed", risk_flags=[]),  # 위험하지만 proceed
            next_steps=[],
        )
        
        gate = apply_decision_gate(issue)
        
        # HIGH_RISK issue는 hold로 상향되어야 함
        self.assertEqual(gate.control, "hold")
        # 원래 control이 proceed였으므로 false negative 위험이 있음
        self.assertTrue(len(gate.false_negative_indicators) > 0)
    
    def test_false_negative_risk_for_low_confidence_proceed(self) -> None:
        """낮은 routing confidence인데 proceed면 false negative 위험 표시"""
        issue = IssueAnalysis(
            issue_id="issue_001",
            product="펀드",
            issue_type="환매지연",
            routing_confidence=0.5,  # LOW_CONFIDENCE_THRESHOLD 미만
            focal={"type": "transaction"},
            target={},
            facts=[],
            missing_facts=[],
            fact_resolution=FactResolution(),
            evidence_refs=[],
            decision=Decision(control="proceed", risk_flags=[]),
            next_steps=[],
        )
        
        gate = apply_decision_gate(issue)
        
        # ask로 상향되어야 함
        self.assertEqual(gate.control, "ask")
        # 원래 control이 proceed였고 confidence가 낮으므로 false negative 위험 표시
        self.assertTrue(len(gate.false_negative_indicators) > 0)


class IssueValidationTests(unittest.TestCase):
    """Test 2. 복합 민원 분리 및 사실관계 추적 검증"""
    
    def test_detects_duplicate_issues(self) -> None:
        """중복 이슈를 감지해야 함"""
        request = CaseAnalyzeRequest(
            case_id="case_001",
            prompt="펀드 환매가 지연됐어요",
            issues=[
                IssueInput(
                    issue_id="issue_001",
                    product="펀드",
                    issue_type="환매지연",
                    text="환매가 지연됐어요",
                ),
                IssueInput(
                    issue_id="issue_002",
                    product="펀드",
                    issue_type="환매지연",  # 중복
                    text="펀드 환매가 늦어졌어요",
                ),
            ],
        )
        
        log = IssueValidator().validate(request)
        
        self.assertFalse(log.is_valid)
        self.assertGreater(len(log.conflicts_detected), 0)
        self.assertGreater(len(log.duplicates_found), 0)
    
    def test_detects_causality_chains(self) -> None:
        """인과관계 체인을 감지해야 함"""
        request = CaseAnalyzeRequest(
            case_id="case_001",
            prompt="금리 안내를 못 받았는데 금리가 다르게 적용됐어요",
            issues=[
                IssueInput(
                    issue_id="issue_001",
                    product="예금",
                    issue_type="금리변경미통지",
                    text="금리 변경을 통지받지 못했어요",
                ),
                IssueInput(
                    issue_id="issue_002",
                    product="예금",
                    issue_type="금리적용오류",
                    text="금리가 잘못 적용됐어요",
                ),
            ],
        )
        
        log = IssueValidator().validate(request)
        
        # 인과관계가 감지돼야 함
        self.assertGreater(len(log.causality_chains), 0)
        # 교정 제안이 있어야 함
        self.assertGreater(len(log.corrections_applied), 0)
    
    def test_marks_as_warning_for_causality_chains(self) -> None:
        """인과관계가 감지되면 warning 이상으로 표시"""
        request = CaseAnalyzeRequest(
            case_id="case_001",
            prompt="복합 민원",
            issues=[
                IssueInput(
                    issue_id="issue_001",
                    product="예금",
                    issue_type="금리변경미통지",
                    text="금리 변경 미통지",
                ),
                IssueInput(
                    issue_id="issue_002",
                    product="예금",
                    issue_type="금리적용오류",
                    text="금리 오류",
                ),
                IssueInput(
                    issue_id="issue_003",
                    product="펀드",
                    issue_type="환매지연",
                    text="환매 지연",
                ),
            ],
        )
        
        log = IssueValidator().validate(request)
        
        # 인과관계가 감지되면 warning 이상이어야 함
        if len(log.causality_chains) > 0:
            self.assertIn(log.severity, ["warning", "critical"])


class ComplianceFilterTests(unittest.TestCase):
    """Test 1. 규칙 우회 방지 범위 확장"""
    
    def test_forbidden_patterns_expanded(self) -> None:
        """확장된 금지 패턴 목록 확인"""
        from server.policy.gateway import FORBIDDEN_CLAIM_PATTERNS
        
        # 핵심 패턴들이 모두 포함되어 있는지
        self.assertIn("보상액", FORBIDDEN_CLAIM_PATTERNS)
        self.assertIn("배상액", FORBIDDEN_CLAIM_PATTERNS)
        self.assertIn("법적 결론", FORBIDDEN_CLAIM_PATTERNS)
        self.assertIn("자동 제출", FORBIDDEN_CLAIM_PATTERNS)
        self.assertIn("위법입니다", FORBIDDEN_CLAIM_PATTERNS)
        # 추가 패턴들
        self.assertIn("소송을 권장", FORBIDDEN_CLAIM_PATTERNS)
        self.assertIn("100% 받을", FORBIDDEN_CLAIM_PATTERNS)


if __name__ == "__main__":
    unittest.main()
