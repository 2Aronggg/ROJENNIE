from __future__ import annotations

import json
import logging
import os
from typing import Any

from pydantic import BaseModel, Field

from server.agents.router import _llm_enabled
from server.policy.gateway import (
    ComplianceViolation,
    LLMPolicyGateway,
    contains_forbidden_claim,
    sanitize_llm_text,
    sanitize_llm_texts,
)
from server.schemas import IssueAnalysis, IssueReport


LOGGER = logging.getLogger(__name__)

DECISION_LABELS = {
    "proceed": "진행",
    "ask": "추가 확인 필요",
    "amend": "보완 필요",
    "hold": "검토 대기",
}

# 민원 유형별로 사용자가 챙겨야 하는 증빙. LLM에게 맡기지 않는 이유는 존재하지 않는
# 서류를 지어내면 사용자가 은행에 가서 헛걸음을 하기 때문이다 - 목록이 고정이라
# 사람이 검토한 값만 나간다.
DOCUMENTS_BY_ISSUE: dict[str, list[str]] = {
    "계약해지_지연": ["계약서 또는 상품설명서", "해지 신청 기록", "금융회사 답변"],
    "금리적용오류": ["상품설명서", "가입 당시 안내 자료", "이자 지급 내역"],
    "인출제한": ["거래내역 또는 화면 캡처", "거부 사유 안내", "금융회사 답변"],
    "거래오류": ["거래내역서", "계산 근거", "상품설명서"],
    "명의도용": ["거래 또는 계좌 개설 알림", "본인 인증 기록", "금융회사 답변"],
    "만기지급거절": ["계약서 또는 상품설명서", "만기일 확인 자료", "금융회사 답변"],
    "우대금리설명부족": ["상품설명서", "우대금리 조건 안내 자료", "가입 당시 상담 기록"],
    "금리변경미통지": ["상품설명서", "금리 변경 안내 자료", "우대조건 안내 자료"],
    "중도해지위약금": ["계약서 또는 상품설명서", "해지 신청 내역", "수수료 산정 내역"],
    "자동이체누락안내": ["자동이체 실패 내역", "우대조건 안내 자료", "알림 수신 내역"],
    "민원처리지연": ["민원 접수 내역", "접수번호", "금융회사 답변 또는 처리 상태"],
    "위험설명부족": ["상품설명서", "위험등급 안내 자료", "가입 당시 상담 기록"],
    "환매지연": ["환매 신청 내역", "예정 지급일 안내", "실제 지급 내역"],
    "수수료미고지": ["상품설명서", "수수료 차감 내역", "가입 당시 안내 자료"],
    "해지절차복잡": ["해지 문의 내역", "금융회사 안내 내용", "계약서 또는 상품설명서"],
    "손실민원부실": ["민원 접수 내역", "손실 관련 거래내역", "금융회사 답변"],
    "원금손실설명부족": ["상품설명서", "위험등급 안내 자료", "가입 당시 상담 기록"],
    "상환금과소지급": ["상환 내역", "상품설명서", "예상 상환금 안내 자료"],
    "배상비율불만": ["배상 안내문", "산정 근거 자료", "금융회사 답변"],
    "중도해지손실": ["중도해지 또는 상환 요청 내역", "손실 산정 내역", "상품설명서"],
    "분쟁조정안내부족": ["민원 접수 내역", "금융회사 답변", "분쟁조정 안내 자료"],
}
DEFAULT_DOCUMENTS = ["계약서 또는 상품설명서", "금융회사 답변", "거래내역"]


class LLMReportDraft(BaseModel):
    complaint_content: str = ""
    issue: str = ""
    processing_result: str = ""
    consumer_cautions: list[str] = Field(default_factory=list)
    used_evidence_chunk_ids: list[str] = Field(default_factory=list)
    reasoning: str = ""
    follow_up_actions: list[str] = Field(default_factory=list)
    evidence_summary: str = ""


REPORT_SYSTEM_PROMPT = """너는 금융소비자 보호 민원 리포트 작성자다.
주어진 민원 사실, 가상 계약·거래 데이터, RAG 검색 후보자료만 사용해 리포트를 정리한다.

규칙:
- 결정 상태는 이미 정해져 있으므로 바꾸지 않는다.
- 자료에 없는 금액, 법적 결론, 사실을 만들어내지 않는다.
- 보상액, 배상액, 책임비율, 법적 구제 가능성, 외부 제출 자동 실행과 같은 추정·결론 성격 표현은 작성하지 않는다.
- RAG 후보자료가 민원과 직접 관련이 낮으면 판단 근거로 단정하지 않는다.
- reasoning은 2~4문장으로, 확인된 사실과 부족한 사실을 구분해 작성한다.
- follow_up_actions는 실제로 확인할 수 있는 후속 조치 2~5개를 작성한다.
- evidence_summary는 검색된 자료가 이 민원에 어떤 의미인지 2~4문장 줄글로 쓴다.
  chunk id나 파일 경로를 쓰지 말고 "예금거래기본약관 제7조"처럼 사람이 부르는 이름으로
  인용한다. 같은 조항이 여러 문서에서 중복 검색되면 한 번만 언급한다. 관련 자료가 없으면
  빈 문자열을 반환한다.
- 반드시 JSON만 반환한다.
"""


def compose_issue_report(
    issue: IssueAnalysis,
    *,
    use_llm: bool | None = None,
    client: Any | None = None,
) -> IssueReport:
    fallback = _fallback_report(issue)
    if not _llm_enabled(use_llm):
        return fallback

    try:
        context = issue.model_dump(mode="json", exclude={"report"})
        response = LLMPolicyGateway(client=client).generate_json(
            stage="report_composer",
            contents=REPORT_SYSTEM_PROMPT
            + "\n\n현재 결정 상태: "
            + DECISION_LABELS.get(issue.decision.control, issue.decision.control)
            + "\n\nReturn JSON fields complaint_content, issue, processing_result, consumer_cautions, used_evidence_chunk_ids, reasoning, follow_up_actions, and evidence_summary. Ground processing_result in the supplied RAG evidence, and use only supplied chunk_id values."
            + "\n\n분석 데이터:\n"
            + json.dumps(context, ensure_ascii=False),
            response_schema=LLMReportDraft.model_json_schema(),
        )
        if not response.text:
            raise ValueError("Gemini returned no report result")
        draft = LLMReportDraft.model_validate_json(response.text)
        _validate_report_draft(draft)
        processing_result = _sanitize_text(draft.processing_result)
        reasoning = _sanitize_text(draft.reasoning) or processing_result
        actions = [item.strip() for item in draft.follow_up_actions if item.strip()][:5]
        cautions = [item.strip() for item in draft.consumer_cautions if item.strip()][:5]
        evidence_ids = {ref.chunk_id for ref in issue.evidence_refs}
        used_evidence = [chunk_id for chunk_id in draft.used_evidence_chunk_ids if chunk_id in evidence_ids]
        if not reasoning:
            raise ValueError("Gemini returned an empty report reason")
        return _scope_report(
            issue,
            IssueReport(
            complaint_content=_sanitize_text(draft.complaint_content) or _complaint_content(issue),
            issue=_sanitize_text(draft.issue) or issue.issue_type,
            processing_result=processing_result or reasoning,
            consumer_cautions=_sanitize_cautions(cautions or actions or fallback.consumer_cautions),
            used_evidence_chunk_ids=used_evidence,
            current_decision=DECISION_LABELS.get(issue.decision.control, issue.decision.control),
            reasoning=reasoning,
            follow_up_actions=_sanitize_actions(actions or fallback.follow_up_actions),
            evidence_summary=_sanitize_text(draft.evidence_summary),
            generated_by="llm",
            ),
        )
    except ComplianceViolation as exc:
        LOGGER.warning("LLM report blocked by compliance policy; using fallback: %s", exc)
        return _compliance_blocked_report(fallback, str(exc))
    except Exception as exc:
        LOGGER.warning("LLM report generation failed; using fallback: %s", exc)
        return fallback


def _fallback_report(issue: IssueAnalysis) -> IssueReport:
    missing = issue.missing_facts
    if missing:
        reasoning = (
            "현재 확인된 사실과 검색 후보자료를 바탕으로 1차 리포트를 생성했습니다. "
            + ", ".join(missing)
            + " 확인 전에는 최종 판단을 확정하기 어렵습니다."
        )
        actions = issue.next_steps or [f"{field} 확인" for field in missing]
    elif issue.evidence_refs:
        reasoning = "입력된 사실과 RAG 검색 후보자료를 함께 검토했습니다. 현재 확인된 범위에서는 추가 확인 절차를 안내합니다."
        actions = issue.next_steps or ["관련 거래내역과 계약 조건 확인"]
    else:
        reasoning = "확인된 사실과 직접 연결되는 근거자료가 부족해 판단을 확정하기 어렵습니다."
        actions = issue.next_steps or ["관련 계약·거래 자료 제출"]
    return _scope_report(issue, IssueReport(
        complaint_content=_complaint_content(issue),
        issue=issue.issue_type,
        processing_result=reasoning,
        consumer_cautions=actions[:5],
        used_evidence_chunk_ids=[ref.chunk_id for ref in issue.evidence_refs[:1]],
        current_decision=DECISION_LABELS.get(issue.decision.control, issue.decision.control),
        reasoning=reasoning,
        follow_up_actions=actions[:5],
        generated_by="fallback",
    ))


def _compliance_blocked_report(report: IssueReport, reason: str) -> IssueReport:
    return report.model_copy(
        update={
            "current_decision": DECISION_LABELS["ask"],
            "compliance_blocked": True,
            "compliance_flags": ["llm_output_forbidden_claim"],
            "compliance_reason": reason,
        }
    )


def _complaint_content(issue: IssueAnalysis) -> str:
    statement = next((fact.value for fact in issue.facts if fact.field == "user_statement"), None)
    return str(statement or issue.issue_type)


# 실제 필터 구현은 server/policy/gateway.py에 있다 - PII 마스킹(redact_pii)과
# 나란히 두어, logic_verification.py 등 다른 LLM 호출부도 같은 패턴 목록을 쓰게 한다.
_sanitize_text = sanitize_llm_text


def _validate_report_draft(draft: LLMReportDraft) -> None:
    values = [
        draft.complaint_content,
        draft.issue,
        draft.processing_result,
        draft.reasoning,
        *draft.consumer_cautions,
        *draft.follow_up_actions,
    ]
    if any(contains_forbidden_claim(value) for value in values):
        raise ComplianceViolation("LLM report crossed compliance boundary")


def _sanitize_cautions(values: list[str]) -> list[str]:
    return sanitize_llm_texts(values)


def _sanitize_actions(values: list[str]) -> list[str]:
    return sanitize_llm_texts(values)


FORBIDDEN_CONCLUSION_PATTERNS = (
    "배상 가능",
    "배상액",
    "보상받을 수",
    "은행 잘못",
    "은행의 잘못",
    "위법",
    "책임이 있습니다",
    "책임이 인정",
    "당신도 받을 수",
    "반드시 지급",
)


def _scope_report(issue: IssueAnalysis, report: IssueReport) -> IssueReport:
    processing_result = _limit_claim_scope(report.processing_result)
    reasoning = _limit_claim_scope(report.reasoning)
    cautions = [_limit_claim_scope(value) for value in report.consumer_cautions]
    actions = [_limit_claim_scope(value) for value in report.follow_up_actions]

    if _has_precedent_only_support(issue):
        precedent_caution = "유사 사례는 참고용이며, 현재 사안의 결론은 확인된 사실과 직접 근거 범위 안에서만 안내됩니다."
        if precedent_caution not in cautions:
            cautions = [precedent_caution, *cautions]

    if issue.logic_verification.unsupported_claims and issue.decision.control == "proceed":
        processing_result = "확인된 사실과 직접 근거가 부족해 결론을 확정하지 않고 추가 확인이 필요합니다."

    return report.model_copy(
        update={
            "processing_result": processing_result,
            "reasoning": reasoning,
            "consumer_cautions": cautions[:5],
            "follow_up_actions": actions[:5],
            "documents_to_prepare": DOCUMENTS_BY_ISSUE.get(issue.issue_type, DEFAULT_DOCUMENTS),
        }
    )


def _limit_claim_scope(value: str) -> str:
    if not value:
        return value
    if any(pattern in value for pattern in FORBIDDEN_CONCLUSION_PATTERNS):
        return "확인된 사실 기준으로 안내할 수 있는 범위만 정리하며, 단정적인 책임 판단은 추가 검토가 필요합니다."
    return value


def _has_precedent_only_support(issue: IssueAnalysis) -> bool:
    evidence_chains = [
        chain for chain in issue.logic_verification.support_chains if chain.supporting_evidence
    ]
    return bool(evidence_chains) and all(
        chain.evidence_role == "precedent_reference" for chain in evidence_chains
    )
