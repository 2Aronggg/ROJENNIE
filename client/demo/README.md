# KB Key Buddy Demo HTML

This folder preserves the static demo screens that were created separately from
the functional React client in `feat/data-server`.

## Files

Each agent demo exists in two variants:

| Agent | Static (`*.html`) | Live (`*-live.html`) |
|---|---|---|
| 1 case builder | `agent1-case-builder.html` | `agent1-case-builder-live.html` |
| 2 hybrid retriever | `agent2-hybrid-retriever.html` | `agent2-hybrid-retriever-live.html` |
| 3 logic verification | `agent3-logic-verification.html` | `agent3-logic-verification-live.html` |
| 4 response composer | `agent4-response-composer.html` | `agent4-response-composer-live.html` |

- **Static**: fully self-contained, scripted visuals. Open directly in a browser.
- **Live**: same screens, but they load `../agent-api.js` and call the running
  FastAPI server. Start the server first, then serve this folder over HTTP
  (opening via `file://` blocks the API calls).

`kb-key-buddy-mobile-flow.html` is a mobile user-flow video mockup (static).

The `-live.html` files were previously `client/index1.html`~`index4.html` in the
client root. They moved here so the root keeps a single product entry point
(`index.html`).

**Known duplication**: the static and live variants of agents 2-4 are identical
except for the `agent-api.js` script tag, and agent 1's two copies have drifted
apart in layout. They are currently maintained as separate files. Consolidating
to one file per agent (loading `agent-api.js` optionally) is tracked in
`docs/TODO.md`.

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
