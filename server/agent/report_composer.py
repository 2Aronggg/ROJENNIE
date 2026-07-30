from __future__ import annotations

import json
import logging
import os
from typing import Any

from pydantic import BaseModel, Field

from server.agent.router import _gemini_client, _llm_enabled
from server.schemas import IssueAnalysis, IssueReport


LOGGER = logging.getLogger(__name__)

DECISION_LABELS = {
    "proceed": "진행",
    "ask": "추가 확인 필요",
    "amend": "보완 필요",
    "hold": "검토 대기",
}


class LLMReportDraft(BaseModel):
    complaint_content: str = ""
    issue: str = ""
    processing_result: str = ""
    consumer_cautions: list[str] = Field(default_factory=list)
    used_evidence_chunk_ids: list[str] = Field(default_factory=list)
    reasoning: str = ""
    follow_up_actions: list[str] = Field(default_factory=list)


REPORT_SYSTEM_PROMPT = """너는 금융소비자 보호 민원 리포트 작성자다.
주어진 민원 사실, 가상 계약·거래 데이터, RAG 검색 후보자료만 사용해 리포트를 정리한다.

규칙:
- 결정 상태는 이미 정해져 있으므로 바꾸지 않는다.
- 자료에 없는 금액, 법적 결론, 사실을 만들어내지 않는다.
- RAG 후보자료가 민원과 직접 관련이 낮으면 판단 근거로 단정하지 않는다.
- reasoning은 2~4문장으로, 확인된 사실과 부족한 사실을 구분해 작성한다.
- follow_up_actions는 실제로 확인할 수 있는 후속 조치 2~5개를 작성한다.
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
        response = (client or _gemini_client()).models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
            contents=REPORT_SYSTEM_PROMPT
            + "\n\n현재 결정 상태: "
            + DECISION_LABELS.get(issue.decision.control, issue.decision.control)
            + "\n\nReturn JSON fields complaint_content, issue, processing_result, consumer_cautions, used_evidence_chunk_ids, reasoning, and follow_up_actions. Ground processing_result in the supplied RAG evidence, and use only supplied chunk_id values."
            + "\n\n분석 데이터:\n"
            + json.dumps(context, ensure_ascii=False),
            config={
                "response_mime_type": "application/json",
                "response_schema": LLMReportDraft.model_json_schema(),
            },
        )
        if not response.text:
            raise ValueError("Gemini returned no report result")
        draft = LLMReportDraft.model_validate_json(response.text)
        processing_result = draft.processing_result.strip()
        reasoning = draft.reasoning.strip() or processing_result
        actions = [item.strip() for item in draft.follow_up_actions if item.strip()][:5]
        cautions = [item.strip() for item in draft.consumer_cautions if item.strip()][:5]
        evidence_ids = {ref.chunk_id for ref in issue.evidence_refs}
        used_evidence = [chunk_id for chunk_id in draft.used_evidence_chunk_ids if chunk_id in evidence_ids]
        if not reasoning:
            raise ValueError("Gemini returned an empty report reason")
        return IssueReport(
            complaint_content=draft.complaint_content.strip() or _complaint_content(issue),
            issue=draft.issue.strip() or issue.issue_type,
            processing_result=processing_result or reasoning,
            consumer_cautions=cautions or actions or fallback.consumer_cautions,
            used_evidence_chunk_ids=used_evidence,
            current_decision=DECISION_LABELS.get(issue.decision.control, issue.decision.control),
            reasoning=reasoning,
            follow_up_actions=actions or fallback.follow_up_actions,
            generated_by="llm",
        )
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
    return IssueReport(
        complaint_content=_complaint_content(issue),
        issue=issue.issue_type,
        processing_result=reasoning,
        consumer_cautions=actions[:5],
        used_evidence_chunk_ids=[ref.chunk_id for ref in issue.evidence_refs[:1]],
        current_decision=DECISION_LABELS.get(issue.decision.control, issue.decision.control),
        reasoning=reasoning,
        follow_up_actions=actions[:5],
        generated_by="fallback",
    )


def _complaint_content(issue: IssueAnalysis) -> str:
    statement = next((fact.value for fact in issue.facts if fact.field == "user_statement"), None)
    return str(statement or issue.issue_type)
