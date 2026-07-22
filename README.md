# egregore

Secure event-driven multi-agent cybersecurity platform with ephemeral sandbox workers, DDD domain policies, and LiteLLM provider abstraction.

Платформа автономных security-агентов: **event ingress → router → worker queue → sandbox → A2A bus → control plane**. Оркестрация — детерминированные правила и политики; LLM — исполнитель внутри изолированного worker run.

## Возможности

- 7 config-driven агентов: 4 **workers** + **planner** + 2 **control** (critic, coordinator)
- Event-driven dispatch: `SecurityEvent` → `EventRouter` → Redis job queue → ephemeral worker
- Sandbox lifecycle: поднялся → выполнил playbook → опубликовал finding → уничтожился
- Control plane: critic (валидация) + coordinator (статус для пользователя) как async bus subscribers
- DDD domain: `events`, `workers`, `findings`, `security` policies
- Secure-by-design: MILS boundaries, A2A envelopes, mTLS metadata, scope/HITL middleware
- Cross-session episodic memory + investigation state (Postgres)
- Durable JobStore (HITL pause/resume survives restart)
- LLM planner for `engagement.start` / `POST /v1/engagements` with sequential worker chain
- Kafka/Redpanda event bus (`USE_KAFKA`), worker daemons, router/critic/coordinator consumers
- MCP Tool Gateway (PEP), HITL L1/L2, DoW job budgets
- Secure RAG (`rag_query`), Skill Gateway (`load_skill`), K8s sandbox connector
- Prometheus metrics, Grafana dashboard, CI adversarial gates
- FastAPI: `POST /events`, `GET /status`, investigations API, SSE stream, HITL resume API, `GET /metrics`
- Operator UI (`web_ui/`): work orders list, live chat, follow-ups, structured intake, persona stepper, approvals, live timeline
- Operator follow-ups on closed work orders: Q&A, orchestrate, catalog re-plan (`POST /v1/work-orders/{id}/follow-ups`)
- Work order API (`/v1/work-orders`) as preferred operator surface over legacy `/v1/engagements`
- Продуктовый слой `agents/` — personas, rules, routing plans, skills
- 100% unit test coverage gate on `cys_core/domain`

## Architecture docs (visual)

For architects and designers: [docs/architecture-site/](../../docs/architecture-site/) in the cxado meta-repo — UML-style Mermaid diagrams, security layers, Egregore backend deep dive.

k3s offline: `https://<host>:30080` after `./scripts/k8s/k3s-deploy-arch-docs-offline.sh`.

Markdown SSOT: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/OBSERVABILITY.md](docs/OBSERVABILITY.md)

## Быстрый старт

Backend is split into fully independent packages — `worker`
(agent-execution runtime), `api` (FastAPI ingress), and `tool-gateway`
(standalone PEP for sandboxed agent tool calls), each with its own
physical copy of domain models/generic infra, no shared package between
them — plus `model-gateway`, a newer, standalone LLM-call chokepoint
(sanitization/guardrails) that exists and is tested but isn't wired into
the runtime or deploy topology yet (see
[docs/MSP_BACKLOG.md](docs/MSP_BACKLOG.md) §29,
§47-49). Current active plan — what's still not done, prioritized (headlined by splitting
`worker` into separate `dispatcher`/`agent-runtime` services):
[docs/MICROSERVICES_SPLIT_PLAN.md](docs/MICROSERVICES_SPLIT_PLAN.md). Full history/reasoning
behind everything already done: `docs/MSP_BACKLOG.md`.

```bash
cd backend/worker && uv sync
cd backend/api && uv sync
cd backend/tool-gateway && uv sync

docker compose -f deploy/docker-compose.yml up -d   # Postgres + Redis + Redpanda + Qdrant

cp backend/api/.env.example backend/api/.env       # LLM API key (local only, not committed)
cp backend/worker/.env.example backend/worker/.env
cp backend/tool-gateway/.env.example backend/tool-gateway/.env

cd backend/api && uv run egregore info
cd backend/api && uv run egregore migrate   # apply migrations/*.sql
```

### Operator UI (full stack)

```bash
make dev-infra                    # or: docker compose -f deploy/docker-compose.yml up -d
cd backend/tool-gateway && uv run egregore tool-gateway --port 8092  # or: make dev-tool-gateway
cd backend/api && uv run egregore serve --port 8080    # or: make dev-api
cd backend/worker && uv run egregore worker --daemon   # optional: make dev-worker

cd web_ui && cp .env.local.example .env.local && bun install && bun run dev
# or from repo root: make dev-web-ui
```

Open [http://localhost:3000](http://localhost:3000). API: [http://localhost:8080/status](http://localhost:8080/status).

**Smoke (consultant advisory):** goal «Как защититься от вирусов?» → Response shows consultant JSON, critic verdict (`critic:{engagement_id}`), coordinator narrative (`coordinator:{engagement_id}`). Enable live chat per [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) §7 (`STREAM_AGENT_OUTPUT=true` on agent-runtime + api, `NEXT_PUBLIC_EGRESS_SSE=1`). If consultant findings are summary-only, re-seed catalog: `uv run egregore catalog seed` (ensures `ConsultantFinding` schema).

**Smoke pitfalls:** use a **new** engagement after code/deploy changes (old `eng-smoke-*` rows may be pytest leftovers in Postgres). Restart `egregore serve` and `egregore worker` after env changes (avoid duplicate worker processes). Integration test [`test_shared_engagement_state`](backend/worker/tests/worker/test_shared_engagement_state.py) uses prefix `eng-test-shared-` and deletes its row — do not confuse with manual smoke.

**Langfuse traces ≠ UI progress:** planner/LLM spans in Langfuse do not mean worker jobs ran — check `worker_jobs.status` and Live events (`job_started`). **`GET /health/infra`** reports `queue.backend`, `queue.depth`, and `workers_hint` (`backlog` vs `processing`).

**Bus-loop symptoms:** thousands of `soc-bus-*` / `network-bus-*` jobs, `LLEN cys:worker:jobs:queue` huge, new engagements stuck at `enqueued`. Purge spam from Redis, fail stuck `running` bus jobs in Postgres, restart a single API + 2 workers. Suppressed/duplicate findings should no longer re-enqueue after phase-5 guards.

If Jobs shows only planner, check `worker_jobs` for the engagement id and that workers are running.

One-command dev (infra + api + worker + ui): `./scripts/dev.sh`

If staged pipeline jobs stay `pending` with a long Redis backlog, flush the worker queue and restart workers (`redis-cli DEL` on the job list key, or restart with an empty queue).

Docker app profile (no host Node/Python): `make dev-docker` (requires `.env`).

### CLI smoke test

```bash
# Ingest SIEM event → enqueue SOC worker (api)
cd backend/api && uv run egregore ingest -t siem.alert -p '{"alert":"powershell encoded command"}' -s high

# Process queued worker job (worker)
cd backend/worker && uv run egregore worker --once

# Control plane status (worker)
cd backend/worker && uv run egregore status

# Manual investigation, all workers (api)
cd backend/api && uv run egregore session -g "Assess CI/CD pipeline risks"

# HTTP API (api)
cd backend/api && uv run egregore serve --port 8080

# Tests (low memory — one pytest process per tests/<dir>/, run per package)
cd backend/worker && ./scripts/pytest_batches.sh --cov --domain-gate  # own copy of cys_core/domain
cd backend/api && ./scripts/pytest_batches.sh --cov --domain-gate     # own copy of cys_core/domain
```

## CLI

`egregore api` commands run from `backend/api/`; `egregore worker` commands run from `backend/worker/`.

| Команда | Пакет | Описание |
|---------|-------|----------|
| `info` | api | Конфигурация, workers, control agents |
| `ingest -t TYPE -p PAYLOAD` | api | Structured event → router → job queue |
| `worker [--once\|--daemon] [--persona soc]` | worker | Обработка jobs из очереди |
| `router` | api | Kafka router consumer (`security.events.raw`) |
| `critic` | worker | Critic bus consumer (`bus.findings`) |
| `coordinator` | worker | Coordinator bus consumer |
| `status` | worker | Snapshot control plane (findings, narratives) |
| `serve [--port 8080]` | api | FastAPI event/status server |
| `session -g "..."` | api | Start engagement (`POST /v1/work-orders` preferred; legacy `POST /v1/engagements`) |
| `migrate` | api | Apply SQL migrations to Postgres |
| `agent <worker>` | worker | Debug: один worker без очереди |
| `adversarial-test` | api | `pytest tests/` |

## Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│  Ingress: CLI / FastAPI / webhooks (SIEM, NetFlow, docs)         │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Control plane (always on)                                       │
│  EventRouter ← agents/plans/*.yaml routing rules                 │
│  CriticService + CoordinatorService ← bus subscribers            │
│  StatusStore → GET /status                                       │
└────────────────────────────┬────────────────────────────────────┘
                             ▼ enqueue
┌─────────────────────────────────────────────────────────────────┐
│  Worker plane (ephemeral)                                        │
│  Redis queue → WorkerOrchestrator → LocalSandbox → AgentRuntime  │
│  → SecureAgentBus → sandbox destroy                              │
└─────────────────────────────────────────────────────────────────┘
```

Подробнее: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Структура репозитория

```
egregore/
├── backend/
│   ├── worker/              # egregore-worker: agent-execution runtime (LangChain/LangGraph),
│   │   │                    #   critic/coordinator daemons, own (now-redundant, kept per §21.6.5)
│   │   │                    #   copy of the Tool Gateway, own copy of cys_core
│   │   │                    #   (domain/application/infrastructure), bootstrap
│   │   ├── src/             # cys_core.{domain,runtime,llm,registry.tools,...}, interfaces.worker/control_plane/gateways
│   │   └── scripts/         # pytest_batches, verify_import_boundaries, …
│   ├── api/                 # egregore-api: FastAPI ingress/CRUD, event routing, HITL resume,
│   │   │                    #   own copy of cys_core (domain/application/infrastructure), bootstrap —
│   │   │                    #   no fastapi-only exception: no langchain/langgraph/deepagents/litellm
│   │   ├── src/              # interfaces.api, cys_core.{domain,application} use_cases (CRUD side)
│   │   └── scripts/
│   ├── tool-gateway/        # egregore-tool-gateway: standalone PEP for sandboxed agent tool calls
│   │   │                    #   (stdlib asyncio server, no FastAPI/langchain), own copy of cys_core
│   │   ├── src/             # cys_core.{domain,application,infrastructure.tools}, interfaces.gateways.tool
│   │   └── scripts/
│   ├── model-gateway/       # egregore-model-gateway: standalone LLM-call chokepoint (sanitize/
│   │   │                    #   guardrail input+output, stdlib asyncio server, no FastAPI/langchain) —
│   │   │                    #   built, tested, but NOT wired into the runtime or deploy topology yet
│   │   │                    #   (§29, §47-49); worker still calls litellm in-process directly today
│   │   ├── src/             # cys_core.domain.security.*, interfaces.gateways.model
│   │   └── scripts/
│   └── agents/              # Product personas, rules, plans, skills — sibling of all four packages
├── deploy/                 # Dockerfile.{api,worker,tool-gateway}, compose, k8s, helm, grafana
├── web_ui/                 # Operator console (Next.js)
├── tui/                    # Operator TUI (Go Bubble Tea)
├── docs/
├── Makefile                # thin dispatcher (Python → backend/{worker,api,tool-gateway}/, UI → web_ui/)
└── scripts/                # full-stack dev wrappers, security gates
```

`backend/contracts/` (an earlier shared domain/ports/infra package) and
`backend/shared/` (the pre-split monolith before that) have both been
retired — worker, api, tool-gateway, and model-gateway are fully independent
packages, see [docs/MSP_BACKLOG.md](docs/MSP_BACKLOG.md)
§18, §21.6, §29.

## Роли агентов

| Роль | Агенты | Жизненный цикл |
|------|--------|----------------|
| `worker` | redteam, network, soc, compliance | Эфемерный: event → sandbox → bus → die |
| `control` | critic, coordinator | Постоянные subscribers, без тяжёлого sandbox |

## Переменные окружения

| Переменная | Default | Описание |
|------------|---------|----------|
| `LLM_MODEL` | `anthropic/claude-sonnet-4` | LiteLLM model |
| `STAGE` | `dev` | `dev` / `test` / `prod` |
| `USE_MEMORY_FALLBACK` | `false` | In-memory queue/sandbox fallback |
| `USE_KAFKA` | `false` | Kafka job queue + bus transport |
| `USE_TOOL_GATEWAY` | `false` | MCP tools via `interfaces.gateways.tool` PEP |
| `USE_QDRANT` | `false` | Qdrant RAG store (else in-memory) |
| `SANDBOX_CONNECTOR` | `local` | `local` \| `k8s` worker sandbox |
| `STATUS_STORE_CONNECTOR` | `auto` | Control plane status (`postgres` in prod) |
| `HITL_AUTO_APPROVE_THRESHOLD` | `low` | Risk gate для dangerous tools |
| `TRUST_SCORE_THRESHOLD` | `0.5` | Critic trust threshold |
| `PERSISTENCE_CONNECTOR` | `auto` | `auto`, `memory`, `postgres` |
| `UI_CORS_ORIGINS` | `http://localhost:3000,...` | Allowed origins for Operator UI (`web_ui/`) |
| `EGREGORE_FOLLOW_UP_ENABLED` | `true` | Enable operator follow-ups on closed work orders |
| `EGREGORE_FOLLOW_UP_PLAN_ENABLED` | `true` | Enable catalog re-plan follow-up mode |
| `EGREGORE_MAX_FOLLOW_UPS` | `10` | Max follow-up messages per engagement |
| `EGREGORE_MAX_FOLLOW_UP_PLANS` | `3` | Max plan-mode follow-ups per engagement |
| `PLANNER_TIMEOUT_SECONDS` | `120` | Fallback when async meta-planner stays in planning |

Полный список: [`backend/api/.env.example`](backend/api/.env.example), [`backend/worker/.env.example`](backend/worker/.env.example)

## Тестирование

```bash
cd backend/worker && ./scripts/pytest_batches.sh --cov --domain-gate  # своя копия cys_core/domain
cd backend/api && ./scripts/pytest_batches.sh --cov --domain-gate     # своя копия cys_core/domain
```

## Документация

| Файл | Содержание |
|------|------------|
| [docs/REFACTOR_COMPLETE.md](docs/REFACTOR_COMPLETE.md) | DDD refactor checklist |
| [AGENTS.md](AGENTS.md) | Правила для AI-ассистентов |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Event-driven architecture, work orders, follow-ups |
| [docs/operator-console-contract.md](docs/operator-console-contract.md) | Operator API/SSE contract (UI + TUI) |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Разработка и отладка |
| [docs/SECURE_DEPLOYMENT.md](docs/SECURE_DEPLOYMENT.md) | Secure deployment |
| [docs/MASTER_PLAN_SECURE_PLATFORM.md](docs/MASTER_PLAN_SECURE_PLATFORM.md) | Production roadmap (Kafka, MCP gateway, RAG, skills) |
| [agents/README.md](agents/README.md) | Продуктовый слой |

## Требования

- Python ≥ 3.13
- Docker (Postgres 16, Redis 7) — опционально с `USE_MEMORY_FALLBACK=true`
- Node.js 20+ — для Operator UI (`web_ui/`)
- API-ключ LLM-провайдера — для live worker runs

## Лицензия

MIT. См. [LICENSE](LICENSE).
