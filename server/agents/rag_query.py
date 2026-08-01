from __future__ import annotations

import json
import logging
import os
from typing import Any

from pydantic import BaseModel, Field

from server.agents.router import _llm_enabled
from server.policy.gateway import LLMPolicyGateway
from server.schemas import IssueInput


LOGGER = logging.getLogger(__name__)


class RAGQueryDraft(BaseModel):
    terms: list[str] = Field(default_factory=list)


class RAGQuery(BaseModel):
    text: str
    variants: list[str] = Field(default_factory=list)
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
    fallback_variants = _query_variants(issue, [])
    fallback = RAGQuery(
        text=fallback_variants[0],
        variants=fallback_variants,
        generated_by="fallback",
    )
    if not _llm_enabled(use_llm):
        return fallback

    try:
        response = LLMPolicyGateway(client=client).generate_json(
            stage="rag_query",
            contents=RAG_QUERY_PROMPT + "\n\n민원:\n" + json.dumps(
                {
                    "product": issue.product,
                    "issue_type": issue.issue_type,
                    "text": issue.text,
                },
                ensure_ascii=False,
            ),
            response_schema=RAGQueryDraft.model_json_schema(),
        )
        if not response.text:
            raise ValueError("Gemini returned no RAG query")
        draft = RAGQueryDraft.model_validate_json(response.text)
        terms = [term.strip() for term in draft.terms if term.strip()][:12]
        if not terms:
            raise ValueError("Gemini returned no RAG terms")
        return RAGQuery(
            text=" ".join([issue.product, *terms]),
            variants=_query_variants(issue, terms),
            generated_by="llm",
        )
    except Exception as exc:
        LOGGER.warning("LLM RAG query generation failed; using lexical query: %s", exc)
        return fallback


def _query_variants(issue: IssueInput, terms: list[str]) -> list[str]:
    focused = " ".join([issue.product, issue.issue_type, *terms, issue.text]).strip()
    term_query = " ".join([issue.product, *terms, issue.text]).strip()
    variants = [focused, term_query, issue.text.strip()]
    return list(dict.fromkeys(query for query in variants if query))[:3]
