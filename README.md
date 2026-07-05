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
- Operator UI (`ui/`): investigations list, persona stepper, approvals, live timeline
- Продуктовый слой `agents/` — personas, rules, routing plans, skills
- 100% unit test coverage gate on `cys_core/domain`

## Architecture docs (visual)

For architects and designers: [docs/architecture-site/](../../docs/architecture-site/) in the cxado meta-repo — UML-style Mermaid diagrams, security layers, Egregore backend deep dive.

k3s offline: `https://<host>:30080` after `./scripts/k8s/k3s-deploy-arch-docs-offline.sh`.

Markdown SSOT: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/OBSERVABILITY.md](docs/OBSERVABILITY.md)

## Быстрый старт

```bash
uv sync

docker compose up -d   # Postgres + Redis + Redpanda + Qdrant

cp .env.example .env   # LLM API key

uv run egregore info
uv run egregore migrate   # apply migrations/*.sql
```

### Operator UI (full stack)

```bash
make dev-infra                    # or: docker compose up -d
uv run egregore serve --port 8080 # or: make dev-api
uv run egregore worker --daemon # optional: make dev-worker

cd ui && cp .env.local.example .env.local && npm install && npm run dev
# or from repo root: make dev-ui
```

Open [http://localhost:3000](http://localhost:3000). API: [http://localhost:8080/status](http://localhost:8080/status).

### Minimal console (no Node)

Lightweight static UI for smoke tests — start investigation, jobs, HITL approvals:

```bash
uv run egregore serve --port 8080
uv run egregore worker --daemon   # when testing worker pipeline
make -C projects/egregore dev-console
```

Open [http://localhost:5173](http://localhost:5173). See [`ui-minimal/README.md`](ui-minimal/README.md).

**Smoke (consultant advisory):** goal «Как защититься от вирусов?» → Response shows consultant JSON, critic verdict (`critic:{engagement_id}`), coordinator narrative (`coordinator:{engagement_id}`). Enable `STREAM_AGENT_OUTPUT=true` and `CRITIC_USE_LLM_JUDGE=true` in local env. If consultant findings are summary-only, re-seed catalog: `uv run egregore catalog seed` (ensures `ConsultantFinding` schema).

**Smoke pitfalls:** use a **new** engagement after code/deploy changes (old `eng-smoke-*` rows may be pytest leftovers in Postgres). Restart `egregore serve` and `egregore worker` after env changes (avoid duplicate worker processes). Integration test [`test_shared_engagement_state`](tests/worker/test_shared_engagement_state.py) uses prefix `eng-test-shared-` and deletes its row — do not confuse with manual smoke.

**Langfuse traces ≠ UI progress:** planner/LLM spans in Langfuse do not mean worker jobs ran — check `worker_jobs.status` and Live events (`job_started`). **`GET /health/infra`** reports `queue.backend`, `queue.depth`, and `workers_hint` (`backlog` vs `processing`).

**Bus-loop symptoms:** thousands of `soc-bus-*` / `network-bus-*` jobs, `LLEN cys:worker:jobs:queue` huge, new engagements stuck at `enqueued`. Purge spam from Redis, fail stuck `running` bus jobs in Postgres, restart a single API + 2 workers. Suppressed/duplicate findings should no longer re-enqueue after phase-5 guards.

If Jobs shows only planner, check `worker_jobs` for the engagement id and that workers are running.

One-command dev (infra + api + worker + ui): `./scripts/dev.sh`

If staged pipeline jobs stay `pending` with a long Redis backlog, flush the worker queue and restart workers (`redis-cli DEL` on the job list key, or restart with an empty queue).

Docker app profile (no host Node/Python): `make dev-docker` (requires `.env`).

### CLI smoke test

```bash
# Ingest SIEM event → enqueue SOC worker
uv run egregore ingest -t siem.alert -p '{"alert":"powershell encoded command"}' -s high

# Process queued worker job
uv run egregore worker --once

# Control plane status
uv run egregore status

# Manual investigation (all workers)
uv run egregore session -g "Assess CI/CD pipeline risks"

# HTTP API
uv run egregore serve --port 8080

# Tests (low memory — one pytest process per tests/<dir>/)
./scripts/pytest_batches.sh --cov --domain-gate
```

## CLI

| Команда | Описание |
|---------|----------|
| `info` | Конфигурация, workers, control agents |
| `ingest -t TYPE -p PAYLOAD` | Structured event → router → job queue |
| `worker [--once\|--daemon] [--persona soc]` | Обработка jobs из очереди |
| `router` | Kafka router consumer (`security.events.raw`) |
| `critic` | Critic bus consumer (`bus.findings`) |
| `coordinator` | Coordinator bus consumer |
| `status` | Snapshot control plane (findings, narratives) |
| `serve [--port 8080]` | FastAPI event/status server |
| `session -g "..."` | Start engagement (`POST /v1/engagements` / `engagement.start`) |
| `migrate` | Apply SQL migrations to Postgres |
| `agent <worker>` | Debug: один worker без очереди |
| `adversarial-test` | `pytest tests/` |

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
├── agents/                 # Продукт: personas, rules, plans, skills
├── bootstrap/              # settings, DI container, product_loader
├── connectors/             # SIEM poll → ingress API
├── interfaces/             # Delivery: api, ingress, worker, control_plane, gateways, rag, cli
├── ui/                     # Operator console (Next.js) — investigations, approvals, SSE
├── deploy/k8s/             # Worker Job + NetworkPolicy
├── deploy/grafana/         # SOC dashboards
├── cys_core/
│   ├── domain/             # events, workers, findings, security, rag, skills
│   ├── application/        # ports, use-cases
│   ├── infrastructure/     # sandbox, queue, bus, kafka
│   ├── observability/      # Prometheus, tracing, Langfuse tags
│   ├── registry/           # AgentRegistry, tools, mcp_tools, skills
│   └── runtime/            # AgentRuntime
├── docs/
├── Makefile                # make dev-infra, dev-api, dev-ui, dev-worker
└── tests/
```

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
| `UI_CORS_ORIGINS` | `http://localhost:3000,...` | Allowed origins for Operator UI (`ui/`) |

Полный список: [`.env.example`](.env.example)

## Тестирование

```bash
./scripts/pytest_batches.sh --cov --domain-gate
```

## Документация

| Файл | Содержание |
|------|------------|
| [docs/REFACTOR_COMPLETE.md](docs/REFACTOR_COMPLETE.md) | DDD refactor checklist |
| [AGENTS.md](AGENTS.md) | Правила для AI-ассистентов |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Event-driven architecture |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Разработка и отладка |
| [docs/SECURE_DEPLOYMENT.md](docs/SECURE_DEPLOYMENT.md) | Secure deployment |
| [docs/MASTER_PLAN_SECURE_PLATFORM.md](docs/MASTER_PLAN_SECURE_PLATFORM.md) | Production roadmap (Kafka, MCP gateway, RAG, skills) |
| [agents/README.md](agents/README.md) | Продуктовый слой |

## Требования

- Python ≥ 3.13
- Docker (Postgres 16, Redis 7) — опционально с `USE_MEMORY_FALLBACK=true`
- Node.js 20+ — для Operator UI (`ui/`)
- API-ключ LLM-провайдера — для live worker runs

## Лицензия

MIT. См. [LICENSE](LICENSE).
