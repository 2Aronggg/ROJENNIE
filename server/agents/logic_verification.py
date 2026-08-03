from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from server.agents.router import _llm_enabled
from server.policy.gateway import LLMPolicyGateway, sanitize_llm_text, sanitize_llm_texts
from server.schemas import EvidenceRef, IssueAnalysis, LogicVerification, SupportChain


LOGGER = logging.getLogger(__name__)


class LLMLogicDraft(BaseModel):
    summary: str = ""
    checks: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)


LOGIC_PROMPT = """You are the Logic Verification Agent for a financial complaint pipeline.
Check only the provided user facts, retrieved evidence, and case analysis.

Rules:
- Separate user-stated facts, system-inferred facts, document evidence, and precedent references.
- Do not turn similar cases or precedents into a direct conclusion.
- Do not create legal conclusions, compensation amounts, or final fault judgments.
- summary, checks, unresolved는 모두 한국어로 쓴다. 사용자에게 그대로 보이는 문장이다.
- Return JSON only with summary, checks, and unresolved.
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
            contents=LOGIC_PROMPT + "\n\nAnalysis data:\n" + json.dumps(context, ensure_ascii=False),
            response_schema=LLMLogicDraft.model_json_schema(),
        )
        if not response.text:
            raise ValueError("Gemini returned no logic verification")
        draft = LLMLogicDraft.model_validate_json(response.text)
        summary = sanitize_llm_text(draft.summary)
        checks = sanitize_llm_texts(draft.checks)[:5]
        unresolved = sanitize_llm_texts(draft.unresolved)[:5]
        if not summary:
            raise ValueError("Gemini returned an empty logic summary")
        return LogicVerification(
            summary=summary,
            checks=checks,
            unresolved=unresolved,
            support_chains=fallback.support_chains,
            unsupported_claims=fallback.unsupported_claims,
            generated_by="llm",
        )
    except Exception as exc:
        LOGGER.warning("LLM logic verification failed; using fallback: %s", exc)
        return fallback


def _fallback_verification(issue: IssueAnalysis) -> LogicVerification:
    checks = ["fact/evidence consistency checked"]
    unresolved = list(issue.missing_facts)
    support_chains = _build_support_chains(issue)

    if issue.evidence_refs:
        checks.append("retrieved evidence was classified by document role")
    else:
        unresolved.append("direct supporting evidence")

    unsupported_claims = [
        chain.claim
        for chain in support_chains
        if chain.inference_type == "unverified" or not chain.allowed_in_final
    ]
    summary = "Confirmed facts and retrieved evidence were checked for support."
    if unresolved:
        summary += " Some inputs still need confirmation: " + ", ".join(unresolved) + "."

    return LogicVerification(
        summary=summary,
        checks=checks[:5],
        unresolved=list(dict.fromkeys(unresolved))[:5],
        support_chains=support_chains,
        unsupported_claims=list(dict.fromkeys(unsupported_claims))[:5],
        generated_by="fallback",
    )


def _build_support_chains(issue: IssueAnalysis) -> list[SupportChain]:
    chains: list[SupportChain] = []
    missing_source_tags = [
        fact.field for fact in issue.facts if not getattr(fact, "source_type", None)
    ]
    if missing_source_tags:
        chains.append(
            SupportChain(
                claim="출처가 기록되지 않은 사실이 있어 그대로 결론에 쓸 수 없습니다",
                supporting_evidence=missing_source_tags,
                inference_type="unverified",
                evidence_role="unknown",
                allowed_in_final=False,
            )
        )

    direct_refs = [ref for ref in issue.evidence_refs if _evidence_role(ref) == "direct_evidence"]
    precedent_refs = [ref for ref in issue.evidence_refs if _evidence_role(ref) == "precedent_reference"]
    guide_refs = [ref for ref in issue.evidence_refs if _evidence_role(ref) == "procedure_guide"]

    if direct_refs:
        chains.append(
            SupportChain(
                claim=f"{issue.issue_type} 판단을 약관·규정 원문이 직접 뒷받침합니다",
                supporting_evidence=[ref.chunk_id for ref in direct_refs[:5]],
                inference_type="direct_match",
                evidence_role="direct_evidence",
                allowed_in_final=True,
            )
        )
    if precedent_refs:
        chains.append(
            SupportChain(
                claim=f"{issue.issue_type} 관련 분쟁 사례가 있으나 참고용으로만 쓸 수 있습니다",
                supporting_evidence=[ref.chunk_id for ref in precedent_refs[:5]],
                inference_type="analogical",
                evidence_role="precedent_reference",
                allowed_in_final=False,
            )
        )
    if guide_refs:
        chains.append(
            SupportChain(
                claim=f"{issue.issue_type}의 다음 절차는 안내 문서로 확인됩니다",
                supporting_evidence=[ref.chunk_id for ref in guide_refs[:5]],
                inference_type="direct_match",
                evidence_role="procedure_guide",
                allowed_in_final=True,
            )
        )
    if not issue.evidence_refs:
        chains.append(
            SupportChain(
                claim=f"{issue.issue_type}: no retrieved evidence supports a substantive conclusion",
                supporting_evidence=[],
                inference_type="unverified",
                evidence_role="unknown",
                allowed_in_final=False,
            )
        )
    return chains


def _evidence_role(ref: EvidenceRef) -> str:
    path = ref.path.lower()
    if any(part in path for part in ("/cases/", "\\cases\\", "cases/", "cases\\", "precedent")):
        return "precedent_reference"
    if any(part in path for part in ("/guides/", "\\guides\\", "guides/", "guides\\", "guide")):
        return "procedure_guide"
    if any(
        part in path
        for part in (
            "/products/",
            "\\products\\",
            "products/",
            "products\\",
            "/regulations/",
            "\\regulations\\",
            "regulations/",
            "regulations\\",
        )
    ):
        return "direct_evidence"
    return "unknown"
