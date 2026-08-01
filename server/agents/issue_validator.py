from __future__ import annotations

import logging
from datetime import datetime
from uuid import uuid4

from server.schemas import CaseAnalyzeRequest, IssueValidationLog


LOGGER = logging.getLogger(__name__)


class IssueValidator:
    """분리된 이슈들의 일관성, 인과관계, 중복을 검증한다.
    
    복합 민원이 제대로 쪼개졌는지, 인과관계가 올바르게 반영됐는지 확인하고,
    필요하면 수정 권장사항을 제시한다.
    """
    
    def validate(self, request: CaseAnalyzeRequest) -> IssueValidationLog:
        issues = request.issues
        if not issues:
            return IssueValidationLog(
                validation_id=str(uuid4()),
                case_id=request.case_id or "unknown",
                total_issues=0,
                is_valid=True,
                severity="clean",
                created_at=datetime.utcnow(),
            )
        
        validation_checks: list[str] = []
        conflicts: list[str] = []
        causality_chains: list[list[str]] = []
        duplicates: list[str] = []
        corrections: list[str] = []
        
        # 1. 동일/중복 이슈 검사
        duplicates, duplicate_warnings = self._detect_duplicates(issues)
        if duplicates:
            conflicts.extend(duplicate_warnings)
            corrections.append(f"중복 이슈 {len(duplicates)}개 감지 - 검토 필요")
        validation_checks.append(f"중복 검사: {len(issues)} 이슈 중 {len(duplicates)}개 중복")
        
        # 2. 인과관계 체인 검사
        chains = self._detect_causality_chains(issues)
        if chains:
            causality_chains.extend(chains)
            for chain in chains:
                validation_checks.append(f"인과관계 체인 감지: {' → '.join(chain)}")
                if len(chain) > 1:
                    # 원인 이슈가 분리됐는지 확인
                    root_issue_id = next((i.issue_id for i in issues if i.issue_type == chain[0]), None)
                    if not root_issue_id:
                        corrections.append(f"원인 이슈({chain[0]}) 누락 - 분리 재검토")
        
        # 3. 필수 정보 일관성 검사
        missing_institutions = self._check_institution_consistency(issues)
        if missing_institutions:
            for issue_id in missing_institutions:
                conflicts.append(f"{issue_id}: 금융회사명 미확인")
            corrections.append("금융회사 정보가 부족한 이슈가 있습니다")
        validation_checks.append(f"금융회사 일관성: {len(issues) - len(missing_institutions)}/{len(issues)}")
        
        # 4. 상품 일관성 검사 (같은 상품 내 관련 이슈가 분리됐는지)
        product_groups = self._group_by_product(issues)
        for product, product_issues in product_groups.items():
            if len(product_issues) > 1:
                related = self._find_related_issues_in_product(product_issues)
                if related:
                    for issue_pair in related:
                        corrections.append(
                            f"{product}: {issue_pair[0]} ↔ {issue_pair[1]} 관련 가능성 - 검토"
                        )
        
        # 5. 시간 일관성 검사
        temporal_issues = self._check_temporal_consistency(issues)
        if temporal_issues:
            for issue_id, reason in temporal_issues:
                conflicts.append(f"{issue_id}: {reason}")
        
        # 심각도 결정
        is_valid = len(conflicts) == 0
        if len(duplicates) > 0 or len(causality_chains) > 1:
            severity = "critical"
        elif len(causality_chains) > 0 or len(conflicts) > 0:
            severity = "warning"
        else:
            severity = "clean"
        
        log = IssueValidationLog(
            validation_id=str(uuid4()),
            case_id=request.case_id or "unknown",
            total_issues=len(issues),
            validation_checks=validation_checks,
            conflicts_detected=conflicts,
            causality_chains=causality_chains,
            duplicates_found=duplicates,
            corrections_applied=corrections,
            created_at=datetime.utcnow(),
            is_valid=is_valid,
            severity=severity,
        )
        
        LOGGER.info(
            "issue_validation validation_id=%s total_issues=%d severity=%s conflicts=%d",
            log.validation_id,
            len(issues),
            severity,
            len(conflicts),
        )
        
        return log
    
    @staticmethod
    def _detect_duplicates(issues: list) -> tuple[list[str], list[str]]:
        """동일한 이슈가 분리됐는지 검사 (같은 상품+이슈타입+시점)"""
        duplicates: list[str] = []
        warnings: list[str] = []
        
        seen: dict[str, str] = {}
        for issue in issues:
            key = (issue.product, issue.issue_type)
            key_str = f"{issue.product}_{issue.issue_type}"
            
            if key_str in seen:
                duplicates.append(issue.issue_id)
                warnings.append(f"중복: {seen[key_str]} ↔ {issue.issue_id}")
            else:
                seen[key_str] = issue.issue_id
        
        return duplicates, warnings
    
    @staticmethod
    def _detect_causality_chains(issues: list) -> list[list[str]]:
        """원인-결과 관계가 있는 이슈들의 체인 감지"""
        causality_patterns = {
            # (원인_이슈, 결과_이슈) 쌍
            ("금리변경미통지", "금리적용오류"): "금리 변경을 안내 안 해서 적용 오류 발생",
            ("우대금리설명부족", "금리적용오류"): "우대금리를 제대로 설명 안 해서 적용 오류",
            ("수수료미고지", "손실민원부실"): "수수료를 안 고지해서 손실 발생",
            ("위험설명부족", "원금손실설명부족"): "위험 설명 부족이 원금손실로 이어짐",
            ("환매지연", "중도해지손실"): "환매가 지연되면서 손실 발생",
        }
        
        chains: list[list[str]] = []
        issue_types = [issue.issue_type for issue in issues]
        
        for (cause, effect), desc in causality_patterns.items():
            if cause in issue_types and effect in issue_types:
                chains.append([cause, effect])
        
        return chains
    
    @staticmethod
    def _check_institution_consistency(issues: list) -> list[str]:
        """금융회사 정보 일관성 검사"""
        missing = []
        for issue in issues:
            # 명의도용, 사기 같은 고위험 이슈는 금융회사 명이 필수
            if issue.issue_type in {"명의도용", "비인가거래"}:
                if not issue.target.get("subject") or issue.target.get("is_unclear"):
                    missing.append(issue.issue_id)
        return missing
    
    @staticmethod
    def _group_by_product(issues: list) -> dict[str, list]:
        """상품별로 이슈를 그룹화"""
        groups: dict[str, list] = {}
        for issue in issues:
            if issue.product not in groups:
                groups[issue.product] = []
            groups[issue.product].append(issue)
        return groups
    
    @staticmethod
    def _find_related_issues_in_product(product_issues: list) -> list[tuple[str, str]]:
        """같은 상품 내에서 관련 가능성 높은 이슈 쌍 찾기"""
        related_pairs = {
            ("금리변경미통지", "금리적용오류"),
            ("우대금리설명부족", "금리적용오류"),
            ("금리변경미통지", "우대금리설명부족"),
        }
        
        result: list[tuple[str, str]] = []
        issue_types = [issue.issue_type for issue in product_issues]
        
        for type1, type2 in related_pairs:
            if type1 in issue_types and type2 in issue_types:
                result.append((type1, type2))
        
        return result
    
    @staticmethod
    def _check_temporal_consistency(issues: list) -> list[tuple[str, str]]:
        """시간 순서 일관성 검사 (원인이 결과보다 먼저 와야 함)"""
        issues_with_dates = [
            (issue.issue_id, issue.issue_type, issue.text)
            for issue in issues
        ]
        
        problems: list[tuple[str, str]] = []
        # 간단한 시간 일관성 검사만 - 실제로는 데이트 추출이 필요함
        # TODO: 각 이슈에서 날짜를 추출하고 비교
        
        return problems


def validate_issues(request: CaseAnalyzeRequest) -> IssueValidationLog:
    """Issue Splitter 결과를 검증한다"""
    return IssueValidator().validate(request)
