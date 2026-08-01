# Logic Audit Layer

KB Key Buddy does not treat retrieval success as decision correctness. Every issue now carries a support audit before the decision gate and report composer.

## Fact Source Tags

Facts must be traceable to one of four source types:

- `USER_STATED`: directly stated by the user.
- `SYSTEM_INFERRED`: inferred by the system from user text or structured data.
- `DOCUMENT_EVIDENCE`: extracted from product terms, manuals, regulations, or transaction evidence.
- `PRECEDENT_REFERENCE`: dispute cases or precedents. These are reference signals, not direct conclusions.

Legacy `Fact` construction defaults to `USER_STATED` so existing tests and fixtures remain compatible, but new pipeline-generated facts should set the source explicitly.

## Evidence Roles

Retrieved evidence is classified by path:

- `direct_evidence`: product manuals, terms, or regulations. These can support bounded next-step guidance.
- `precedent_reference`: dispute cases or precedents. These can only be phrased as similar-case trends.
- `procedure_guide`: complaint filing, dispute mediation, refund support, or institution procedure guides. These can support next-action guidance only.
- `unknown`: not trusted for a substantive conclusion.

## Support Chain

`LogicVerification.support_chains[]` records:

- `claim`
- `supporting_evidence[]`
- `inference_type`: `direct_match`, `analogical`, or `unverified`
- `evidence_role`
- `allowed_in_final`

Rules:

- `unverified` claims become `unsupported_claim` / `unverified_claim` risk signals.
- `precedent_reference` with `analogical` inference is not allowed as a final direct conclusion.
- If only precedent evidence supports a proceeding claim, the decision gate downgrades `proceed` to `ask`.
- Report composer adds cautionary wording for precedent-only support.

## Control Semantics

| Control | Meaning | Must Not Mean |
| --- | --- | --- |
| `proceed` | The system can guide the next step within confirmed facts and direct evidence. | Final legal/fault/compensation conclusion. |
| `ask` | More user facts or direct evidence are needed. | Failure; it is a safety stop. |
| `amend` | User-facing text or data scope needs correction, masking, or confirmation. | Substantive decision. |
| `hold` | Risk is high enough that automatic handling should stop for human review. | Rejection of the user claim. |

Note: the current schema does not have a separate `review` control. In the implemented backend, review is represented as `hold` with human-review metadata/risk reasons.

## Current Code Mapping

| Step | Module |
| --- | --- |
| Fact source schema | `server/schemas.py` |
| Support verification | `server/agents/logic_verification.py` |
| Control downgrade | `server/agents/decision_gate.py` |
| Final wording guard | `server/agents/report_composer.py` |
| Regression tests | `server/tests/test_logic_audit.py` |

## Measured Guardrail Tests

`server/tests/test_logic_audit.py` verifies:

- no evidence + `proceed` is downgraded to `ask`
- precedent-only evidence + `proceed` is downgraded to `ask`
- direct product/regulatory evidence can remain `proceed` when no other risks exist
