from __future__ import annotations

import json
import logging
import os
from typing import Any

from pydantic import BaseModel, Field

from server.agents.router import _llm_enabled
from server.policy.gateway import LLMPolicyGateway
from server.schemas import IssueAnalysis, LogicVerification


LOGGER = logging.getLogger(__name__)


class LLMLogicDraft(BaseModel):
    summary: str = ""
    checks: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)


LOGIC_PROMPT = """너는 금융 민원의 Logic Verification Agent다.
사용자 사실, 가상 계약·거래 데이터, RAG 검색 후보자료 사이의 연결을 검증한다.

규칙:
- 제공된 데이터와 후보자료만 사용한다.
- 법적 결론이나 최종 결정은 내리지 않는다.
- 확인된 연결, 비교해야 할 조건, 아직 확인할 수 없는 내용을 구분한다.
- summary는 2~4문장, checks와 unresolved는 각각 1~5개로 작성한다.
- 반드시 JSON만 반환한다.
"""


def verify_issue_logic(
    issue: IssueAnalysis,
    *,
    use_llm: bool | None = None,
    client: Any | None = None,
) -> LogicVerification:
    fallback = _fallback_verification(issue)
    if not _llm_enabled(use_llm):
        return fallback

    try:
        context = issue.model_dump(mode="json", exclude={"logic_verification", "report"})
        response = LLMPolicyGateway(client=client).generate_json(
            stage="logic_verification",
            contents=LOGIC_PROMPT + "\n\n분석 데이터:\n" + json.dumps(context, ensure_ascii=False),
            response_schema=LLMLogicDraft.model_json_schema(),
        )
        if not response.text:
            raise ValueError("Gemini returned no logic verification")
        draft = LLMLogicDraft.model_validate_json(response.text)
        summary = draft.summary.strip()
        checks = [item.strip() for item in draft.checks if item.strip()][:5]
        unresolved = [item.strip() for item in draft.unresolved if item.strip()][:5]
        if not summary:
            raise ValueError("Gemini returned an empty logic summary")
        return LogicVerification(
            summary=summary,
            checks=checks,
            unresolved=unresolved,
            generated_by="llm",
        )
    except Exception as exc:
        LOGGER.warning("LLM logic verification failed; using fallback: %s", exc)
        return fallback


def _fallback_verification(issue: IssueAnalysis) -> LogicVerification:
    checks = ["민원 사실과 가상 계약·거래 데이터를 대조"]
    unresolved = list(issue.missing_facts)
    if issue.evidence_refs:
        checks.append("RAG 검색 후보자료의 상품·적용일·조항을 확인")
    else:
        unresolved.append("직접 연결되는 근거자료")
    summary = "확인된 사실과 검색 후보자료의 연결을 점검했습니다."
    if unresolved:
        summary += " " + ", ".join(unresolved) + " 확인이 남아 있습니다."
    return LogicVerification(
        summary=summary,
        checks=checks[:5],
        unresolved=list(dict.fromkeys(unresolved))[:5],
        generated_by="fallback",
    )
