from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ScopeResult:
    text: str
    allowed_fields: list[str]
    excluded_fields: list[str]
    masked_fields: list[str]
    requires_user_confirmation: bool
    warnings: list[str]

    def as_dict(self) -> dict:
        return {
            "allowed_fields": self.allowed_fields,
            "excluded_fields": self.excluded_fields,
            "masked_fields": self.masked_fields,
            "requires_user_confirmation": self.requires_user_confirmation,
            "warnings": self.warnings,
        }


RESIDENT_REGISTRATION_RE = re.compile(r"(?<!\d)(\d{6})-?([1-4])(\d{6})(?!\d)")
PHONE_RE = re.compile(r"(?<!\d)(01[016789])-?(\d{3,4})-?(\d{4})(?!\d)")
CARD_RE = re.compile(r"(?<!\d)(\d{4})[- ]?(\d{4})[- ]?(\d{4})[- ]?(\d{4})(?!\d)")
ACCOUNT_RE = re.compile(r"(?<!\d)(\d{2,6})-(\d{2,6})-(\d{2,8})(?!\d)")
AUTH_CODE_RE = re.compile(r"(?:인증번호|보안코드|OTP|비밀번호)\s*[:：]?\s*([A-Za-z0-9]{4,12})", re.IGNORECASE)

EXCLUDED_FIELDS = [
    "password",
    "security_card",
    "irrelevant_third_party_pii",
    "irrelevant_medical_or_income_info",
]
BASE_ALLOWED_FIELDS = [
    "product",
    "issue_type",
    "text_span",
    "date_or_duration",
    "amount",
    "rate",
    "product_name",
    "institution",
    "requested_action",
]


def apply_content_scope(text: str) -> ScopeResult:
    masked = text
    masked_fields: list[str] = []

    masked, changed = RESIDENT_REGISTRATION_RE.subn(lambda m: f"{m.group(1)}-*******", masked)
    if changed:
        masked_fields.append("resident_registration_number")

    masked, changed = PHONE_RE.subn(lambda m: f"{m.group(1)}-****-{m.group(3)}", masked)
    if changed:
        masked_fields.append("phone_number")

    masked, changed = CARD_RE.subn(lambda m: f"{m.group(1)}-****-****-{m.group(4)}", masked)
    if changed:
        masked_fields.append("card_number")

    masked, changed = ACCOUNT_RE.subn(lambda m: _mask_account(m.group(1), m.group(2), m.group(3)), masked)
    if changed:
        masked_fields.append("account_number")

    masked, changed = AUTH_CODE_RE.subn(lambda m: m.group(0).replace(m.group(1), "*" * len(m.group(1))), masked)
    if changed:
        masked_fields.append("auth_or_password")

    masked_fields = _dedupe(masked_fields)
    warnings = ["민감정보가 감지되어 표시용 텍스트에서 마스킹했습니다."] if masked_fields else []
    return ScopeResult(
        text=masked,
        allowed_fields=BASE_ALLOWED_FIELDS,
        excluded_fields=EXCLUDED_FIELDS,
        masked_fields=masked_fields,
        requires_user_confirmation=bool(masked_fields),
        warnings=warnings,
    )


def _mask_account(first: str, middle: str, last: str) -> str:
    visible_tail = last[-2:] if len(last) >= 2 else last
    return f"{first}-{'*' * len(middle)}-{'*' * max(len(last) - len(visible_tail), 0)}{visible_tail}"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
