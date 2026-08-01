# Privacy Handling

Current backend logic is designed to avoid making unnecessary final judgments, but privacy handling is not complete enough for production.

## Sensitive Fields

Sensitive inputs include account numbers, resident registration numbers, phone numbers, customer identifiers, transaction histories, authentication logs, and free-text complaint details that may reveal identity.

## Current Status

- LLM-facing text is routed through `server/policy/gateway.py`, which already contains content-scope and forbidden-claim guardrails.
- Some masking/scope signals are handled by `decision_gate.py` through `pii_detected`, `masking_required`, and `scope_review_required`.
- Full end-to-end storage minimization and deterministic PII redaction are not yet guaranteed.

## Required Before Production

- Deterministic masking before persistence and before any LLM call.
- Field-level storage policy for account numbers, IDs, and transaction records.
- Audit logs that record masking status without storing raw secrets.
- Tests covering Korean account-number, phone-number, and resident-number patterns.
