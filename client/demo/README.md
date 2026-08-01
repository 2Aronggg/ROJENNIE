# KB Key Buddy Demo HTML

This folder preserves the static demo screens that were created separately from
the functional React client in `feat/data-server`.

## Files

- `agent1-case-builder.html`: Agent 1 case-splitting demo.
- `agent2-hybrid-retriever.html`: Agent 2 retrieval demo.
- `agent3-logic-verification.html`: Agent 3 logic verification demo.
- `agent4-response-composer.html`: Agent 4 response composition demo.
- `kb-key-buddy-mobile-flow.html`: Mobile app user-flow video mockup.

Open any file directly in a browser. The files are self-contained HTML/CSS/JS
except for image and font assets referenced from `client/assets` or remote font
CDNs.

## Difference From The Functional Client

The `feat/data-server` client is a React/Vite application. It uses:

- `client/index.html`
- `client/package.json`
- `client/src/main.jsx`
- `client/src/style.css`

It connects to the FastAPI server and calls real endpoints such as:

- `POST /api/v1/cases/analyze`
- `GET /api/v1/cases/{case_id}`
- `POST /api/v1/cases/{case_id}/review`
- mock customer finance endpoints under `/mock/customers/CUST-001`
- dictionary search under `/dictionary/search`

These demo HTML files do not call those APIs. They are scripted visual demos.
They use fixed text, fixed evidence cards, CSS animations, and small local JS
timers to simulate the product flow.

## Functional Gaps

Compared with `feat/data-server`, these demos do not implement:

- React state management.
- React Flow issue/fact graph rendering.
- Server-backed issue splitting.
- RAG candidate retrieval.
- Dictionary lookup.
- Mock customer deposit, savings, and loan data retrieval.
- LocalStorage case history.
- Generated complaint report persistence.
- Human review API flow.
- Editable issue/fact nodes.
- Real drawer interactions backed by case data.

## Scenario Gap

The functional client currently centers on deposit and savings examples:

- deposit maturity interest mismatch.
- savings rate-change or preferential-rate notice issues.
- customer profile `CUST-001`.

The mobile flow demo uses a different story:

- ELS maturity loss.
- mistaken transfer return.
- privacy guidance.

So the demo is useful for product storytelling and visual direction, but it is
not a faithful UI shell for the current `feat/data-server` feature set.

## Merge Recommendation

Keep the React/Vite client as the main application. Preserve this folder as
presentation material, and link to these files from a docs page or demo route if
needed. Do not replace `client/src/main.jsx` with these static files unless the
goal is to discard the functional client.
