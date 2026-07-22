# Operator Console Contract (UI + TUI)

Единый контракт для **web UI** (`ui/`) и **terminal UI** (`tui/`). Цель — чтобы любой клиент (Next.js, Bubble Tea, мобилка, CLI) подключался к одному и тому же backend без догадок.

**Принцип:** backend определяет данные и события; клиенты реализуют **одинаковую семантику**, но могут отличаться **презентацией**.

---

## 1. Слои

```
FastAPI (interfaces/)          ← источник истины: REST + SSE
        │
        ▼
Operator HTTP contract       ← этот документ + web_ui/lib/api-client.ts
        │
   ┌────┴────┐
   ▼         ▼
 ui/       tui/
 (React)   (Go/Bubble Tea)
```

| Слой | Где живёт | Менять когда |
|------|-----------|--------------|
| API routes & payloads | Python `interfaces/` | новый endpoint, смена JSON |
| HTTP client + types | `web_web_ui/lib/api-client.ts` | **первым** при любом API change |
| Go client + types | `tui/internal/api/` | порт из `api-client.ts` |
| Live chat state machine | `web_web_ui/lib/engagement-chat-state.ts` | новый SSE `type` / `phase` |
| Go chat state | `tui/internal/chat/state.go` | зеркало `engagement-chat-state.ts` |
| JSON/finding display | `web_web_ui/lib/json-display.ts`, `finding-display.ts` | новые маркеры finding/planner |
| Go JSON display | `tui/internal/jsonfmt/` | зеркало json/finding display |
| Экраны / навигация | `web_ui/app/(operator)/`, `tui/internal/ui/` | UX, не контракт |

**Не дублировать бизнес-логику в UI/TUI.** Если правило одинаковое для обоих клиентов — оно в shared-модуле (TS) или явно портировано в Go с тестом.

---

## 2. Словарь (важно при переписывании)

| Термин в API | Термин в UI | Примечание |
|--------------|-------------|------------|
| `engagement` | `investigation` / **work order** | UI переименовывает для оператора; ID один: `engagement_id` = `work_order_id` = `investigation_id` |
| `job` | job / agent run | Один worker run, ключ чата: `job_id` |
| `persona` | persona | Имя агента из catalog |
| `workspace_id` | workspace | Контекст кастомных worker-персон; передаётся в `POST /v1/work-orders` |
| `organization_id` / `tenant_id` | tenant | Auth boundary; JWT `organization_id` должен совпадать с `tenant_id` при `AUTH_ENABLED=1` |
| `planner:{engagement_id}` | synthetic job | Виртуальная строка чата для плана |
| `critic:{engagement_id}` | control job | Quality gate verdict (**UI: only on fail/revision**, not pass) |
| `coordinator:{engagement_id}` | control job | Engagement progress summary (not final report; see `final_report`) |
| HITL | approval | `POST /jobs/{id}/resume` |

---

## 3. Operator flows (capability matrix)

Клиент **должен** уметь эти потоки. Реализация (таблица, viewport, sidebar) — на усмотрение клиента.

| Flow | Web route | TUI | Обязательные действия |
|------|-----------|-----|------------------------|
| List investigations | `/` | Operator Console → Work orders (section 2) | list, sort by `updated_at`, refresh |
| Start investigation | `/` Start card | `n` overlay + goal | `POST /v1/work-orders` (preferred) or legacy `POST /v1/engagements` |
| Watch live run | `/work-orders/[id]` | Right panel: Chat tab | detail + jobs + SSE + hydrate findings/planner |
| HITL inline | chat on investigation | Chat tab `a`/`x` | `GET /approvals/pending` filter by job, `POST /jobs/{id}/resume` |
| Approvals queue | `/approvals` | Approvals section (3) | list, approve/reject с confirm, Enter → jump to WO |
| Catalog browse | `/catalog` | Catalog section (5) | agents, tools, skills, plans, memory sub-tabs |
| Agent detail | `/catalog/agents/[name]` | Catalog Enter → right panel | `GET /catalog/agents/{name}` |
| Skill detail | collapsible in agent | Catalog Enter (skills) | `GET /catalog/skills/{id}` |
| Tool / plan detail | table only (web) | Catalog Enter | из list payload (отдельного GET нет) |
| Memory feed | Catalog Memory tab | Catalog `m` + `/` filter | `GET /v1/memory?tenant_id&agent&limit` |
| Memory detail | `/catalog/memory/[id]` | Catalog Enter (memory) | из list (scan по id) |
| Infra hint | home banner | Status section (1) | `GET /health/infra` |

Legacy TUI (`EGREGORE_TUI_LEGACY=1`): screens `1` Investigations, `2` Watch, `3` Approvals, `4` Catalog — same flows, full-screen navigation.

### Вне контракта v1 (не блокируют паритет)

- Status pie charts (web only)
- Mermaid planner diagrams (web only; клиенты показывают structured text/JSON)
- Login stub / session cookie (web); TUI — env token
- `POST /catalog/reload`, catalog PUT/edit
- `sendInvestigationFollowUp` — legacy path; prefer `POST /v1/work-orders/{id}/follow-ups`
- `/runs`, `/eval`, `/compare` (удалены из web)

---

## 4. HTTP contract

**Канон:** `web_web_ui/lib/api-client.ts`  
**Порт:** `tui/internal/api/client.go` + `types.go`

### Auth & tenant

| Правило | Web | TUI |
|---------|-----|-----|
| Header | `Authorization: Bearer <token>` | то же |
| Tenant | query `tenant_id` (default `default`) | env `EGREGORE_TENANT_ID` |
| Workspace | `workspace_id` in create payload/detail; `X-Workspace-Id` for gateway/BFF context | env `EGREGORE_WORKSPACE_ID` when available |
| Base URL | browser: `/api/egregore` proxy; SSR: upstream | `EGREGORE_API_URL` напрямую |
| Timeout | `NEXT_PUBLIC_EGREGORE_API_TIMEOUT_MS` (20s) | `EGREGORE_API_TIMEOUT_MS` |

Web OIDC uses `/api/auth/login` → `/api/auth/callback` and stores the access token in an httpOnly `egregore_session` cookie. The Next.js `/api/egregore/*` BFF forwards requests to FastAPI and injects `Authorization: Bearer <access_token>` server-side; clients should not read the token from JavaScript except for the explicit local fallback `NEXT_PUBLIC_ALLOW_LOCAL_TOKEN=1`.

### Endpoints (operator scope)

| Method | Path | Назначение |
|--------|------|------------|
| GET | `/health` | features: `stream_agent_output`, `stream_agent_tools` |
| GET | `/health/infra` | workers hint, queue depth |
| GET | `/v1/work-orders?tenant_id&limit&cursor` | список work orders (preferred); `next_cursor` в ответе; invalid `cursor` → 400 |
| GET | `/investigations?tenant_id&limit&cursor` | legacy list; тот же cursor contract + `next_cursor` |
| POST | `/v1/work-orders` | старт: `{ goal?, intake?, profile_id?, intent_mode?, tenant_id? }` — `intent_mode`: `plan\|qa\|auto` |
| GET | `/v1/work-orders/{id}?tenant_id` | detail work order (`initial_follow_up_id` = `wo-{id}`) |
| POST | `/v1/work-orders/{id}/follow-ups` | operator follow-up (preferred); `mode` same as `intent_mode` |
| GET | `/v1/work-orders/{id}/follow-ups?tenant_id` | full operator transcript (initial `wo-*` + follow-ups `fu-*`) |
| GET | `/v1/engagements?tenant_id&limit` | **deprecated** — список investigations |
| POST | `/v1/engagements` | **deprecated** — старт: `{ goal, tenant_id?, ... }` |
| GET | `/v1/engagements/{id}?tenant_id` | **deprecated** detail |
| GET | `/v1/engagements/{id}/stream?tenant_id` | **SSE** live events (shared id with work order) |
| GET | `/v1/engagements/{id}/events?tenant_id` | poll fallback (optional) |
| POST | `/v1/engagements/{id}/follow-ups` | **deprecated** follow-up alias |
| GET | `/v1/engagements/{id}/follow-ups?tenant_id` | **deprecated** follow-up list |
| GET | `/investigations/{id}/jobs?tenant_id` | job list для сортировки чата (`follow_up_id` optional) |
| GET | `/status/stream` | global SSE (optional) |
| GET | `/approvals/pending` | HITL queue |
| POST | `/jobs/{id}/resume` | `{ decision: "approve"\|"reject", approval_id? }` |
| GET | `/catalog/agents` | `{ agents: [...] }` |
| GET | `/catalog/agents/{name}` | agent + `system_prompt` |
| GET | `/catalog/skills`, `/catalog/skills/{id}` | skills |
| GET | `/catalog/tools` | tools |
| GET | `/catalog/plans` | plans |
| GET | `/v1/memory?tenant_id&agent&limit` | tenant memory |

Все JSON field names — **snake_case** как в API. Go struct tags / TS types должны совпадать.

### Investigation detail mapping

Web helper `mapEngagementToInvestigation()` — единственное место, где `EngagementSummary` становится `InvestigationDetail`. TUI делает то же в `api/client.go` при `GetInvestigation`.

Обязательные поля для Watch:

- `goal`, `status`, `planner_plan`, `planner_rationale`, `planner_sub_goals`, `planner_depends_on`
- `findings_summary[]` с `job_id`, `persona`, `finding`
- `final_report`, `execution_mode`, `synthesis_persona`
- `completed_personas`, `failed_personas`

---

## 5. SSE contract (engagement stream)

### Env gates (dev / operator console)

| Env | Package | Effect |
|-----|---------|--------|
| `NEXT_PUBLIC_EGRESS_SSE=1` | `web_ui` | Browser opens `GET /v1/engagements/{id}/stream` (via `/api/egregore` proxy) |
| `STREAM_AGENT_OUTPUT=true` | `agent-runtime` (job executor) | Publishes `assistant_delta`, `assistant_done`, planner/critic gated `assistant_snapshot` |
| `STREAM_AGENT_TOKEN_STREAMING=true` | `agent-runtime` | Token-by-token `assistant_delta` (requires `STREAM_AGENT_OUTPUT` + LLM streaming) |
| `STREAM_AGENT_OUTPUT=true` | `api` | `/health` → `features.stream_agent_output`; `stream_agent_tools` only when both output+tools true |
| `EGRESS_BATCH_SECONDS=0` | `agent-runtime` | Optional: per-token publish instead of 50ms batch |

**K3s cluster:** same vars in Helm ConfigMap `egregore-env`; agent-runtime Job pods inherit via `envFrom`. `TOOL_HITL_MODE=enforce` on cluster. See [`docs/deploy/K3S.md`](deploy/K3S.md).

**Finding snapshot (ungated):** when a worker finding is persisted (`append_engagement_finding`), backend always emits `assistant_snapshot` with formatted finding text — independent of `STREAM_AGENT_OUTPUT`. Ensures chat shows the answer on job complete without page refresh.

**Known limitation:** `consultant` on `AgentRunKernel` path does not attach `stream_context` yet — live `assistant_delta` may not appear during the run; finding snapshot + detail hydrate still apply.

**Формат:** стандартный SSE, каждый `data:` — JSON `EngagementStreamEvent`:

```json
{
  "type": "assistant_delta",
  "phase": "",
  "ts": "2026-...",
  "payload": { "job_id": "...", "delta": "..." }
}
```

### Event types (клиент обязан понимать)

| `type` | Поведение клиента |
|--------|-------------------|
| `assistant_delta` | append `payload.delta` к buffer job |
| `assistant_snapshot` | set/replace buffer (live planner/critic when `STREAM_AGENT_OUTPUT`; **always** on finding save); dedupe если buffer == text |
| `assistant_done` | push buffer → turns, clear buffer |
| `reasoning_delta` | update reasoning block (SGR) |
| `tool_start` / `tool_done` / `tool_error` | если `features.stream_agent_tools`; payload включает `tool_call_id` (LangChain `run_id`); `playbook_search` на `tool_start` — whitelisted `tool_args` (`query`, `limit`, `subdomain`); `tool_done` может нести `output_preview` (≤800 chars) |
| `skill_loaded` | tool row `load_skill → {name}` |
| `status` + `phase=job_started` | `entry.streaming = true`; show spinner until deltas/snapshot |
| `status` + `phase=job_finished` | job error / success; use `formatJobFailure({ error, reason })`; refetch detail (+ delayed retry) |
| `status` + `phase=final_report` | set buffer from `payload.report.summary` when present |
| `control` / `control_error` / `report` | synthetic job (`critic:` / `coordinator:`) |
| `error`, `job_started`, `planning_done`, … | `shouldRefreshOnEvent` → refetch detail |
| `follow_up_queued` | operator follow-up accepted; map `job_id` → `follow_up_id` |
| `follow_up_plan_started` | catalog re-plan running; disable composer until WO `closed` |
| `follow_up_complete` | Q&A/orchestrate answer; payload may include `finding`, `content_type` |
| `outcome_ready` | Canonical `OperatorOutcome` in `payload.outcome` (multi-agent synthesis complete) |
| `follow_up_plan_complete` | plan synthesis done; `finding` holds plan snapshot + summary |
| `follow_up_failed` | mark operator + assistant turns failed |
| `hitl_pending` | attach approval to `job_id` entry; show inline approve/reject in chat |
| `hitl_resolved` | update approval status (`approve`/`reject`/`edit`); refresh jobs on resolve |

**Follow-up job routing:** jobs whose id matches `-fu-` (orchestrator) stream into the follow-up thread, not main `entries`. Specialist jobs spawned during a plan carry `follow_up_id` in job payload — filter them from top-level chat and group under the follow-up pair (`GET /investigations/{id}/jobs` exposes `follow_up_id`).

**Follow-up complete payload (minimum):**

```json
{
  "follow_up_id": "fu-abc",
  "job_id": "consultant-fu-…",
  "persona": "consultant",
  "work_kind": "follow_up_qa",
  "content_type": "finding",
  "text": "{…json…}",
  "finding": { "topic": "…", "summary": "…", "recommendations": [] }
}
```

`finding` wins over `text` on reload (`GET /v1/work-orders/{id}/follow-ups` returns `finding` on assistant turns).

**TUI detail tabs:** Chat · Jobs · Findings · Intake (no separate Follow-ups tab). Follow-up Q/A pairs render in the Chat timeline after the final report (`GroupFollowUpPairs` / `RenderFollowUpPairs`). Composer (`m`, `Ctrl+Enter`) is pinned at the bottom of the Chat tab when the work order is `closed`.

**Канон state machine:** `web_web_ui/lib/engagement-chat-state.ts`  
**Порт:** `tui/internal/chat/state.go` — функции `ApplyEvent`, `EventDedupeKey`, `ShouldRefreshOnEvent`, `HydrateFromDetail`, `SortEntries`, `IsInvestigationTerminal` должны вести себя одинаково.

### Feature flags (`GET /health`)

```ts
type ApiFeatures = {
  streamAgentOutput: boolean  // stream_agent_output
  streamAgentTools: boolean   // stream_agent_tools
}
```

Если `stream_agent_tools === false` — tool events игнорируются.

### Planner synthetic job

```ts
plannerJobId(engagementId) => `planner:${engagementId}`
```

При hydrate из detail без SSE — заполнить buffer планом (structured JSON / formatted text).

### Control job IDs

```ts
resolveControlJobId(type, payload, engagementId):
  report      → coordinator:{engagementId}
  else        → critic:{engagementId}
```

---

## 6. Chat entry model (shared shape)

Оба клиента держат `Map<job_id, Entry>`:

| Field | Type | Notes |
|-------|------|-------|
| `jobId` | string | |
| `persona` | string | default `"agent"` |
| `buffer` | string | streaming text |
| `turns` | string[] | completed assistant messages |
| `reasoning` | object \| null | SGR fields |
| `tools` | array | `{ name, status, tool_call_id?, tool_args?, playbook_result?, error_message? }` — `playbook_search`: query на start, hits из `output_preview` на done |
| `streaming` | bool | |
| `jobError` | string | machine error code |
| `isControlError` | bool | |

**Сортировка строк чата:** planner first → personas по `planner_plan` order → остальные jobs. См. `sortChatEntries` / `SortEntries`.

---

## 7. JSON display contract

Агенты возвращают prose + JSON в одном сообщении. Клиенты **не показывают сырой glue** (`}Здравствуйте`).

| Payload kind | Detection | Render |
|--------------|-----------|--------|
| Planner | `personas[]` or `planner_plan[]` or `sub_goals` | formatted plan (personas chain, rationale, deps) |
| Finding | keys from `FINDING_MARKERS` | summary, risk, evidence, … |
| Mixed text | prose + embedded `{` | split, format JSON block, wrap prose |
| Other JSON | valid `{` or `[` | pretty-print |

**Канон:** `web_web_ui/lib/json-display.ts`, `web_web_ui/lib/finding-display.ts`  
**Порт:** `tui/internal/jsonfmt/`

При добавлении нового finding field — обновить `FINDING_MARKERS` **и** Go `findingMarkers`.

---

## 8. Job error strings (machine → human)

Одинаковый mapping в `formatJobError` / `formatJobError`:

| Prefix | Message |
|--------|---------|
| `tools_not_executed:` | Tools planned but never executed |
| `empty_finding:` | Missing finding fields (list after `:`) |
| `empty_finding` | Model refused / invalid JSON |
| `model_refusal:` | Model refused |
| default | `Job failed: {err}` |

---

## 9. HITL (approvals)

```ts
type PendingApproval = {
  job_id, session_id, persona, tool_name,
  tool_args, risk_level, approval_id,
  correlation_id  // work order / engagement id for deep-link to chat
}
```

`hitl_pending` SSE payload matches `PendingApproval` fields (snake_case). `hitl_resolved` payload: `{ job_id, approval_id, decision, actor }`.

Resume:

```http
POST /jobs/{job_id}/resume
{ "decision": "approve" | "reject", "approval_id": "..." }
```

Watch показывает approval только для jobs текущего investigation. Approvals screen — global queue.

### Chat auto-approve (catalog-driven, UI-only)

Catalog agents may set `hitl_auto_approve: true` in `agent.yaml` (exposed on `GET /catalog/agents`). When **both** are true:

1. Persona has `hitl_auto_approve: true` in catalog
2. Web UI has `NEXT_PUBLIC_HITL_CHAT_AUTO_APPROVE=1`

…the chat client auto-calls `POST /jobs/{job_id}/resume` with `{ decision: "approve", approval_id, actor: "chat-auto-approve" }` on `hitl_pending` (or hydrate). This does **not** bypass server-side HITL pause — the job still enters `AWAITING_APPROVAL` first. Not enabled on `/approvals` inbox.

---

## 10. Catalog contract

Read-only в обоих клиентах.

| Tab | List fields (min) | Detail source |
|-----|-------------------|---------------|
| Agents | name, role, enabled/trust, `hitl_auto_approve` | `GET /catalog/agents/{name}` |
| Tools | tool_id, name, description, risk_tier | list row |
| Skills | skill_id, name, approval_status | `GET /catalog/skills/{id}` |
| Plans | plan_id, name, personas[], active | list row |
| Memory | id, content, source_agent, memory_type | list row (+ `content_parsed`) |

Memory filter: query param `agent` on `GET /v1/memory`.

---

## 11. Как переписать клиент (чеклист)

### Новый endpoint

1. Добавить route в FastAPI + тест
2. Добавить функцию + тип в `web_web_ui/lib/api-client.ts`
3. Порт в `tui/internal/api/`
4. Обновить эту таблицу в §4
5. Подключить на нужном экране

### Новый SSE event type

1. Документировать payload в `docs/platform/TRACE_EVENT_TAXONOMY.md` (если platform-wide)
2. Добавить ветку в `applyChatEvent` (TS)
3. Порт в `chat/state.go` + тест
4. Обновить `shouldRefreshOnEvent` если нужен refetch

### Новый operator screen

1. Добавить строку в §3 capability matrix
2. Реализовать: **load → state → render** (не смешивать)
3. Использовать существующий api client, не raw fetch
4. Для live data — SSE или poll по `shouldRefreshOnEvent`

### Полная замена UI или TUI

1. Скопировать §4 endpoints — не вызывать лишнего
2. Портировать `engagement-chat-state` целиком (самая хрупкая часть)
3. Портировать `json-display` / `finding-display`
4. Прогнать smoke: start investigation → watch SSE → approval → catalog tabs
5. Сверить parity table в `web_ui/README.md` / `tweb_ui/README.md`

---

## 12. Файлы-ориентиры (quick map)

```
projects/egregore/
├── docs/operator-console-contract.md   ← этот файл
├── web_ui/
│   ├── lib/api-client.ts               ← HTTP SSOT
│   ├── lib/engagement-chat-state.ts    ← chat SSOT
│   ├── lib/json-display.ts
│   ├── lib/finding-display.ts
│   └── app/(operator)/                 ← routes
└── tui/
    ├── internal/api/                   ← HTTP port
    ├── internal/chat/                  ← chat port
    ├── internal/jsonfmt/               ← display port
    └── internal/ui/                    ← screens
```

---

## 13. Smoke scenarios (ручная регрессия)

1. **List** — engagements возвращаются, таблица не пустая при данных в API
2. **Start** — `POST` → новый id → открывается watch
3. **SSE** — `assistant_delta` стримится, после done — turn в истории
4. **Planner** — до SSE виден plan из detail hydrate
5. **Finding** — structured summary, не raw JSON blob
6. **HITL** — pending → approve → job продолжается
7. **Catalog** — все 5 табов, enter → detail
8. **Memory filter** — `agent=` сужает список
9. **Follow-up Q&A** — closed WO → composer → `follow_up_complete` в чате
10. **Follow-up plan** — closed WO → plan mode → `follow_up_plan_started` (composer disabled) → specialists enqueued → `follow_up_plan_complete`
