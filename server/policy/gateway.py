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
                "response_schema": dict(response_schema),
            },
        )
        text = getattr(response, "text", "") or ""
        safe_text, output_redactions = redact_pii(text)
        if not safe_text.strip():
            raise ValueError("LLM returned no structured output")
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
