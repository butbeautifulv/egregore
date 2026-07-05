# Egregore minimal console

Static operator UI for local smoke tests — **no Node.js / Next.js**.

## Quick start

```bash
# Terminal 1 — API
cd projects/egregore
uv run egregore serve --port 8080

# Terminal 2 — worker (when testing full pipeline)
uv run egregore worker --daemon

# Terminal 3 — minimal UI
make dev-console
# http://localhost:5173
```

## Features

| Tab | API |
|-----|-----|
| **New** | `POST /v1/engagements` (`plan_strategy: meta_llm`, `mode: async`) |
| **Engagements** | `GET /v1/engagements`, detail + `GET /investigations/:id/jobs` |
| **Approvals** | `GET /approvals/pending`, `POST /jobs/:id/resume` |
| **Engagement stream** | `GET /v1/engagements/:id/stream` (per-engagement SSE) |
| **Findings** | `GET /v1/engagements/:id` → `findings_summary[]` |
| **Catalog** | `GET /catalog/agents`, `/tools`, `/skills`, `/plans` |
| **Agent memory** | `GET /v1/engagements/:id/memory?agent=` (Jobs → Memory) |
| **Langfuse** | header link → filter by `engagement_id` |

## Config (header)

- **API** — default `http://127.0.0.1:8080` (saved in `localStorage`)
- **Token** — optional `Authorization: Bearer` when `AUTH_ENABLED=true`
- **Langfuse** — default `http://localhost:3001`

CORS: API must allow `http://localhost:5173` (default in `UI_CORS_ORIGINS`).

## Full Operator UI

Production console: [`../ui/`](../ui/) (Next.js).
