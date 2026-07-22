# Egregore Operator UI

Next.js operator console — lives at `web_ui/` inside the [egregore](..) repository.

**Shared contract with TUI:** [../docs/operator-console-contract.md](../docs/operator-console-contract.md) — API, SSE, chat state, JSON display. Change API here (`lib/api-client.ts`) first, then port to `tui/internal/api/`.

## Full-stack dev (recommended)

From the meta-repo root:

```bash
# 1. Infra (postgres, redis, qdrant)
cd projects/egregore && docker compose up -d

# 2. Secrets — copy deploy/secrets/egregore-local.env.example → deploy/.secrets/egregore-local.env
#    Set DEEPSEEK_API_KEY, STREAM_AGENT_OUTPUT=true, STREAM_AGENT_TOOLS=true

# 3. API + workers + UI
./scripts/dev.sh
```

- API: http://localhost:8080
- UI: http://localhost:3000

## Quick start (UI only)

```bash
cd web_ui
cp .env.local.example .env.local
bun install
bun run dev
```

API must be running on `http://localhost:8080`.

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `NEXT_PUBLIC_EGREGORE_API_URL` | `http://localhost:8080` | Public API base (docs only; browser uses proxy) |
| `EGREGORE_API_UPSTREAM` | `http://127.0.0.1:8080` | Server-side proxy target |
| `NEXT_PUBLIC_EGREGORE_API_TOKEN` | — | Optional Bearer token when API auth is enabled |
| `NEXT_PUBLIC_EGREGORE_API_TIMEOUT_MS` | `20000` | Client REST fetch timeout (ms) |
| `EGREGORE_API_PROXY_TIMEOUT_MS` | `25000` | Next.js `/api/egregore` upstream timeout for non-SSE (ms) |
| `EGREGORE_AUTH_UI_ENFORCED` | — | Set to `1` to require UI login cookie before operator routes |
| `EGREGORE_DEMO_TOKEN` | `egregore-demo-token` | Token stored in session cookie by `/api/auth/login` stub |
| `NEXT_PUBLIC_LANGFUSE_HOST` | `http://localhost:3001` | External Langfuse UI (optional; not embedded) |
| `NEXT_PUBLIC_EGRESS_SSE` | `1` in dev example | Per-engagement SSE for live agent chat on `/work-orders/[id]`; requires backend `STREAM_AGENT_OUTPUT=true` — see [../docs/DEVELOPMENT.md](../docs/DEVELOPMENT.md) §7 |

## Data loading (REST vs SSE)

| Page | Transport | Endpoints |
|------|-----------|-----------|
| `/` (home) | **REST JSON** | `GET /api/egregore/v1/work-orders` (fallback: `/v1/engagements`) for the table; Start card renders without waiting |
| `/work-orders/[id]` | REST + **SSE** | `GET` work order/engagement + jobs + `Accept: text/event-stream` for live agent tokens. Header badge **Stream connected** when SSE is open. See [../docs/DEVELOPMENT.md](../docs/DEVELOPMENT.md) §7 |

Home does **not** use SSE. If the work order list fails or times out, the Start card stays visible; only the table shows an error.

### Smoke check (corp network / k3s `:30301`)

From a client machine (replace host):

```bash
BASE="https://10.8.185.15:30301"
curl -k -sf "$BASE/api/egregore/health" && echo " health OK"
curl -k -sf "$BASE/api/egregore/v1/work-orders?tenant_id=default&limit=1" | head -c 200 && echo
```

In browser DevTools → Network: `engagements` should return 200 within ~20s, not stay pending forever.

## GUI component library

See [docs/GUI_VENDOR.md](docs/GUI_VENDOR.md) — `vendor/gui` is Egregore's own component library, DataTable included.

## Navigation

| Item | Route | Notes |
|------|-------|-------|
| Work orders | `/` | Start work order card + list; detail at `/work-orders/[id]` as full-height chat |
| Approvals | `/approvals` | HITL tool approvals |
| Catalog | `/catalog` | Agents / tools / skills / plans / **Memory** tab; agent row opens `/catalog/agents/[name]`; memory entry at `/catalog/memory/[id]` |

Auth UI shell: `/login` (no app shell). Set `EGREGORE_AUTH_UI_ENFORCED=1` to gate operator routes. Logout via sidebar user menu.

Redirects (bookmarks): `/investigations/:id` → `/work-orders/:id`; `/runs`, `/traces` → `/`; `/eval`, `/compare`, `/catalog/runtime` → `/catalog`; `/memory` → `/catalog?tab=memory` (preserves `?agent=`).

## Home layout

Home (`/`) stacks vertically: status charts → Start work order card (full width) → work orders table.

## k3s offline UI

Helm values (`deploy/k8s/cxado-offline/values-egregore-offline.yaml`): `ui.replicas: 2`. Deployment uses `strategy: Recreate` so rolling updates do not need a spare pod under tight `cxado-app-cap` quota (`limits.cpu` 6000m). Apply `deploy/k8s/resource-guardrails/cxado-app-quota.yaml` before scaling UI to 2 replicas.

## Feature parity

| Feature | Status |
|---------|--------|
| Start work order (`POST /v1/work-orders`, fallback engagements) | yes |
| Work orders DataTable | yes |
| Engagement chat thread (SSE, inline HITL) | yes |
| Catalog agent detail (prompt / skills / tools / memory) | yes |
| Tenant memory feed (Catalog Memory tab) | yes |
| Approvals DataTable | yes |
| Infra / worker banner | yes |
| Rich findings + final report | yes |
| Follow-up composer (Ask / Reinvestigate / plan) | yes |
| Structured intake on start | yes |
| Status charts on home | yes |
| Interactive conductor (`/runs`) | removed (HTTP API is stub) |
| Catalog quality / compare tabs | removed (trust on agent row + drawer) |
| In-app Langfuse traces iframe | removed (use external Langfuse) |

## Scripts

- `bun run dev` — development server
- `bun run build` — production build
- `bun run typecheck` — TypeScript check
- `bun run lint` — ESLint

## Terminal UI

A Bubble Tea **Operator Console** TUI lives at [`../tui`](../tui) — master-detail layout (work orders + live detail tabs). Legacy full-screen mode: `EGREGORE_TUI_LEGACY=1`. Same API contract as this web UI.

```bash
cd ../tui && make run
```

See [../tui/README.md](../tui/README.md) for env vars and keybindings.
