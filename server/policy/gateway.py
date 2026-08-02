from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from hashlib import sha256
from types import SimpleNamespace
from typing import Any, Mapping


LOGGER = logging.getLogger(__name__)

ALLOWED_STAGES = frozenset(
    {"issue_splitter", "rag_query", "logic_verification", "report_composer"}
)


class PolicyDenied(RuntimeError):
    """Raised when an LLM request fails the local policy check."""


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    stage: str
    policy_version: str = "local-v1"
    reason: str = ""


_PII_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "resident_registration_number",
        re.compile(r"(?<!\d)\d{6}-[1-4]\d{6}(?!\d)"),
        "[주민번호]",
    ),
    (
        "card_number",
        re.compile(r"(?<!\d)(?:\d{4}[-\s]){3}\d{4}(?!\d)"),
        "[카드번호]",
    ),
    (
        "account_number",
        re.compile(r"(?<!\d)(?!(?:01[016789])[-\s])\d{3,6}-\d{2,6}-\d{4,8}(?!\d)"),
        "[계좌번호]",
    ),
    (
        "phone_number",
        re.compile(r"(?<!\d)01[016789][-\s]?\d{3,4}[-\s]?\d{4}(?!\d)"),
        "[전화번호]",
    ),
    (
        "email",
        re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?![\w.-])"),
        "[이메일]",
    ),
)


def redact_pii(value: str) -> tuple[str, int]:
    """Mask direct identifiers while preserving amounts, rates, and dates."""
    redacted = value
    count = 0
    for _, pattern, replacement in _PII_PATTERNS:
        redacted, matches = pattern.subn(replacement, redacted)
        count += matches
    return redacted, count


# 프롬프트에 "단정적 결론·보상액 추정을 쓰지 마라"고 지시하는 것만으로는 LLM이 그
# 지시를 어겨도 걸러낼 방법이 없다. PII처럼 후처리 시점에 실제로 걸러낸다 - 이 목록에
# 걸리면 해당 텍스트 전체를 버리고 호출부가 자기 fallback으로 대체하게 한다.
# 00_SHARED_RULES.md의 15개 공통 규칙 + 확장 컴플라이언스 규칙을 모든 LLM 출력에 적용
FORBIDDEN_CLAIM_PATTERNS: tuple[str, ...] = (
    # 금지된 법적 결론
    "법적 결론",
    "법률상",
    "위법입니다",
    "불완전판매입니다",
    "계약위반입니다",
    
    # 보상·배상 추정 (금지)
    "보상액",
    "배상액",
    "배상비율",
    "책임비율",
    "보상받",
    "배상받",
    "환급될 것",
    "환급됩니다",
    "환급받을",
    
    # 자동 외부제출 지시 (금지)
    "자동 제출",
    "외부 제출",
    "제출하겠습니다",
    "신청하겠습니다",
    "접수하겠습니다",
    
    # 부정확한 법적 조언
    "소송을 권장",
    "민사소송을",
    "형사고소를",
    "손해배상청구를",
    "가압류를",
    
    # 명백한 거짓/환상
    "반드시 성공",
    "확실히",
    "100% 받을",
)

FORBIDDEN_CLAIM_REGEXES: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:불완전\s*판매|위법|계약\s*위반|은행(?:의)?\s*잘못)(?:입니다|이다|으로\s*보입니다|로\s*판단|에\s*해당)", re.IGNORECASE),
    re.compile(r"(?:약\s*)?\d[\d,]*(?:만\s*)?원(?:\s*(?:정도|가량|내외))?\s*(?:환급|배상|보상)(?:\s*(?:예상|가능|가능성|받을|됩니다|될\s*것))", re.IGNORECASE),
    re.compile(r"(?:환급|배상|보상)(?:액|금|비율)?\s*(?:은|이|으로)?\s*(?:약\s*)?\d[\d,]*(?:만\s*)?원", re.IGNORECASE),
    re.compile(r"(?:환급|배상|보상)\s*(?:될\s*것|됩니다|받을\s*수|가능성이\s*높)", re.IGNORECASE),
    re.compile(r"(?:민원|신청서|분쟁조정|소송|고소).{0,12}(?:자동\s*)?(?:제출|접수|신청)하겠습니다", re.IGNORECASE),
    re.compile(r"(?:반드시|확실히|100%)\s*(?:성공|환급|배상|보상|받을)", re.IGNORECASE),
)


def contains_forbidden_claim(value: str) -> bool:
    """Return True when LLM output asserts legal liability or compensation."""
    text = value.strip()
    if not text:
        return False
    lowered = text.lower()
    return any(pattern.lower() in lowered for pattern in FORBIDDEN_CLAIM_PATTERNS) or any(
        pattern.search(text) for pattern in FORBIDDEN_CLAIM_REGEXES
    )


def sanitize_llm_text(value: str) -> str:
    """Drop LLM-authored text that crosses into legal conclusions or compensation estimates.

    Returns "" (not a partial edit) when a forbidden pattern is found, so callers
    fall back to their own deterministic template instead of shipping a
    half-redacted sentence.
    
    Used across ALL LLM output paths:
    - report_composer.py
    - logic_verification.py
    - rag_query.py (검색어 생성)
    - Any future LLM stages
    """
    text = value.strip()
    if not text:
        return ""
    if contains_forbidden_claim(text):
        return ""
    return text


def sanitize_llm_texts(values: list[str]) -> list[str]:
    """Apply sanitization to a list of texts, filtering out empty results."""
    return [item for item in (sanitize_llm_text(value) for value in values) if item]


def _strip_additional_properties(schema: Any) -> Any:
    """Gemini Developer API rejects additionalProperties in response schemas."""
    if isinstance(schema, dict):
        schema.pop("additionalProperties", None)
        for value in schema.values():
            _strip_additional_properties(value)
    elif isinstance(schema, list):
        for item in schema:
            _strip_additional_properties(item)
    return schema


def evaluate_policy(stage: str, contents: str) -> PolicyDecision:
    if stage not in ALLOWED_STAGES:
        return PolicyDecision(False, stage, reason="unsupported_llm_stage")
    if not isinstance(contents, str) or not contents.strip():
        return PolicyDecision(False, stage, reason="empty_llm_payload")
    return PolicyDecision(True, stage)


class LLMPolicyGateway:
    """One deterministic policy boundary for every upstream LLM request."""

    def __init__(self, client: Any | None = None, model: str | None = None) -> None:
        self.client = client
        self.model = model

    def generate_json(
        self,
        *,
        stage: str,
        contents: str,
        response_schema: Mapping[str, Any],
        payload: Mapping[str, Any] | None = None,
    ) -> Any:
        decision = evaluate_policy(stage, contents)
        if not decision.allowed:
            self._audit(decision, contents, redactions=0, payload=payload)
            raise PolicyDenied(decision.reason)

        safe_contents, input_redactions = redact_pii(contents)
        request_hash = _hash_text(safe_contents)
        self._audit(
            decision,
            safe_contents,
            redactions=input_redactions,
            payload=payload,
            request_hash=request_hash,
        )

        client = self.client or _default_client()
        response = client.models.generate_content(
            model=self.model or _default_model(),
            contents=safe_contents,
            config={
                "response_mime_type": "application/json",
                "response_schema": _strip_additional_properties(json.loads(json.dumps(dict(response_schema)))),
            },
        )
        text = getattr(response, "text", "") or ""
        safe_text, output_redactions = redact_pii(text)
        if not safe_text.strip():
            raise ValueError("LLM returned no structured output")
        if contains_forbidden_claim(safe_text):
            raise ValueError("LLM output failed compliance validation")
        try:
            json.loads(safe_text)
        except json.JSONDecodeError as exc:
            raise ValueError("LLM returned invalid JSON") from exc

        self._audit(
            decision,
            safe_text,
            redactions=output_redactions,
            payload=payload,
            request_hash=request_hash,
            event="response",
        )
        return SimpleNamespace(text=safe_text, raw=response)

    @staticmethod
    def _audit(
        decision: PolicyDecision,
        value: str,
        *,
        redactions: int,
        payload: Mapping[str, Any] | None,
        request_hash: str | None = None,
        event: str = "request",
    ) -> None:
        LOGGER.info(
            "llm_policy event=%s stage=%s allowed=%s reason=%s policy=%s redactions=%d payload_hash=%s request_hash=%s",
            event,
            decision.stage,
            decision.allowed,
            decision.reason,
            decision.policy_version,
            redactions,
            _hash_payload(payload),
            request_hash or _hash_text(value),
        )


def _default_client() -> Any:
    # Lazy import avoids loading the provider SDK when rule fallback is used.
    from server.agents.router import _gemini_client

    return _gemini_client()


def _default_model() -> str:
    import os

    return os.getenv("GEMINI_MODEL", "gemini-3.5-flash")


def _hash_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()[:16]


def _hash_payload(payload: Mapping[str, Any] | None) -> str:
    if payload is None:
        return "-"
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return _hash_text(serialized)
