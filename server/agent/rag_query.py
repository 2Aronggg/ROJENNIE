from __future__ import annotations

import json
import logging
import os
from typing import Any

from pydantic import BaseModel, Field

from server.agent.router import _gemini_client, _llm_enabled
from server.schemas import IssueInput


LOGGER = logging.getLogger(__name__)


class RAGQueryDraft(BaseModel):
    terms: list[str] = Field(default_factory=list)


class RAGQuery(BaseModel):
    text: str
    generated_by: str = "fallback"


RAG_QUERY_PROMPT = """너는 금융소비자 보호 RAG 검색어 생성기다.
민원 원문을 법령·약관·상품설명서·분쟁사례에서 찾기 좋은 한국어 검색어로 변환한다.

규칙:
- 답변이나 법적 결론을 작성하지 않는다.
- 원문에 있는 금융상품과 쟁점을 유지한다.
- 검색에 유용한 핵심 용어를 6~12개 반환한다.
- 금액·날짜·금리 등 원문에 없는 사실을 추가하지 않는다.
- 반드시 JSON 형식으로만 반환한다.
"""


def build_rag_query(
    issue: IssueInput,
    *,
    use_llm: bool | None = None,
    client: Any | None = None,
) -> RAGQuery:
    fallback = RAGQuery(
        text=f"{issue.product} {issue.issue_type} {issue.text}",
        generated_by="fallback",
    )
    if not _llm_enabled(use_llm):
        return fallback

    try:
        response = (client or _gemini_client()).models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
            contents=RAG_QUERY_PROMPT + "\n\n민원:\n" + json.dumps(
                {
                    "product": issue.product,
                    "issue_type": issue.issue_type,
                    "text": issue.text,
                },
                ensure_ascii=False,
            ),
            config={
                "response_mime_type": "application/json",
                "response_schema": RAGQueryDraft.model_json_schema(),
            },
        )
        if not response.text:
            raise ValueError("Gemini returned no RAG query")
        draft = RAGQueryDraft.model_validate_json(response.text)
        terms = [term.strip() for term in draft.terms if term.strip()][:12]
        if not terms:
            raise ValueError("Gemini returned no RAG terms")
        return RAGQuery(
            text=" ".join([issue.product, *terms]),
            generated_by="llm",
        )
    except Exception as exc:
        LOGGER.warning("LLM RAG query generation failed; using lexical query: %s", exc)
        return fallback
