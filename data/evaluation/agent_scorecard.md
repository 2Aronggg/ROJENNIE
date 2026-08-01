# KB Key Buddy Agent Scorecard

Generated from `data/evaluation/eval_results.json`.

## Executive Summary

| Metric | Result |
| --- | ---: |
| Eval cases | 24 |
| Issue count accuracy | 87.5% |
| Status exact accuracy | 33.3% |
| Status safety accuracy | 87.5% |
| Evidence recall, case-level | 87.5% |
| Missing-info coverage | 87.5% |

Interpretation: the pipeline is generally conservative. It rarely under-escalates relative to the labels, but it often asks for more information where the label expects `proceed`. From a consumer-protection standpoint this is safer than premature conclusions, but it creates avoidable friction.

## 9-Stage Scorecard

| Stage | Component | Primary Metric | Current Result | Finding |
| --- | --- | --- | ---: | --- |
| 1 | Input Intake / Policy Gateway | UI excluded; prompt accepted for evaluation | Covered by 24 cases | Needs full pytest dependency cleanup |
| 2 | Issue Splitter | Expected issue count accuracy | 87.5% | Good baseline; complex 3+ issue cases remain risk area |
| 3 | Focal Builder | Missing-info coverage | 87.5% | Mostly conservative; labels should be expanded with field aliases |
| 4 | Fact Resolver | Conflict/missing propagation | Indirectly covered | Needs dedicated conflict-labeled dataset |
| 5 | RAG Query Builder | Evidence-bearing query success | Indirectly covered | Works for product/guide; semantic phrasing still weak |
| 6 | RAG Retriever | Case-level evidence recall | 87.5% | Remaining misses are mostly semantic/case-law phrasing |
| 7 | Decision Gate | Status safety accuracy | 87.5% | Strong safety posture; exact status low due to over-asking |
| 8 | Logic Verification | Not scored independently | Pending | Needs contradiction-focused labels |
| 9 | Report Composer | Grounding not scored in this eval | Pending | Existing report grounding evaluator should be run after dependency cleanup |

## Decision Gate Safety

Priority policy: `hold > amend > ask > proceed`.

| Error Type | Meaning | Consumer-Protection Risk | Current Observation |
| --- | --- | --- | --- |
| False negative | Risky case allowed to proceed | High | Lower risk; status safety is 87.5% |
| False positive | Safe/proceedable case escalated to ask/hold | Medium | Common; exact status is only 33.3% |

The asymmetric risk is intentional: false negatives are more harmful because they can produce unsupported financial conclusions. False positives are less harmful but reduce usability and should be reduced with better fact availability and guide/procedure routing.

## Main Failure Themes

1. Product and guide lookup cases often have correct evidence but are still classified as `ask` because the local-only evaluator has no authenticated customer facts.
2. Case-law phrasing still misses some canonical documents when the query uses a broad legal paraphrase.
3. Complex multi-issue prompts are directionally handled, but precise issue count remains below target.
4. Evidence and status labels need alias-aware evaluation; exact text field matching is stricter than the user experience requires.

## Submission Readiness

Ready:
- Ground-truth E2E dataset exists.
- Reproducible E2E evaluator exists.
- Retrieval evaluation includes products, cases, and guide documents.
- Conservative decision-gate behavior is visible in metrics.

Not yet complete:
- Full pytest environment is not clean because optional `google.genai` and `mcp` dependencies are missing.
- Semantic rerank is designed but not executed.
- Canonical dedup mapping is partial.
- Report composer grounding is not integrated into the E2E score.
