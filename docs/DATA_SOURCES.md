# Data Sources

This project mixes real reference data, normalized public-data extracts, and synthetic/demo cases. The boundary must stay visible in demos and reports.

## Real Or Public Reference Data

- KB product manuals, product terms, and related financial documents under `data/corpus` / generated RAG chunks.
- KB complaint process guide data derived from the user-provided KB 민원 접수/처리 text.
- Consumer dispute/case materials added to the corpus where source text was provided or normalized.

## Synthetic Or Demo Data

- User-flow HTML demo text and staged mobile screens.
- Evaluation complaints in `data/evaluation/service_eval_dataset.json`; these are test prompts with ground-truth labels for system behavior, not real customer records.
- Agent demo HTML files and visual traces.

## Operational Rule

Real reference data may support retrieval and procedural guidance. Synthetic/demo data may support evaluation and presentation only. Demo data must not be presented as a real customer case or real institution decision.
