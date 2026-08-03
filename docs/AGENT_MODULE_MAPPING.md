# Agent To Module Mapping

The presentation may describe "Agent 1~4" as conceptual pipeline agents. In the current codebase, these are implemented mainly as Python functions and modules, not independent autonomous services.

> This file duplicates `ARCHITECTURE.md` section 5, which is the canonical version and also carries the Korean presentation wording. Keep them in sync or drop this one.

| Presentation Agent | Conceptual Role | Main Modules |
| --- | --- | --- |
| Agent 1 Case Builder | Split a complex complaint into structured issues and facts. | `server/agents/router.py`, `server/agents/focal_builder.py`, `server/agents/facts.py` |
| Agent 2 Evidence/RAG | Build queries and retrieve relevant product/case/guide chunks. | `server/agents/rag_query.py`, `server/rag/retrieval.py` |
| Agent 3 Logic/Decision | Check fact-evidence support and choose `proceed/ask/amend/hold`. | `server/agents/logic_verification.py`, `server/agents/decision_gate.py` |
| Agent 4 Response | Compose safe user-facing issue reports and next actions. | `server/agents/report_composer.py` |

Use this wording in presentations: "Agent is a logical pipeline role. The submitted prototype implements these roles as backend modules and deterministic functions, with optional LLM calls behind policy gates."
