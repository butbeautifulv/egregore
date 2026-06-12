# cys-agi

Secure event-driven multi-agent cybersecurity platform with ephemeral sandbox workers, DDD domain policies, and LiteLLM provider abstraction.

Платформа автономных security-агентов: **event ingress → router → worker queue → sandbox → A2A bus → control plane**. Оркестрация — детерминированные правила и политики; LLM — исполнитель внутри изолированного worker run.

## Возможности

- 6 config-driven агентов: 4 **workers** (redteam, network, soc, compliance) + 2 **control** (critic, coordinator)
- Event-driven dispatch: `SecurityEvent` → `EventRouter` → Redis job queue → ephemeral worker
- Sandbox lifecycle: поднялся → выполнил playbook → опубликовал finding → уничтожился
- Control plane: critic (валидация) + coordinator (статус для пользователя) как async bus subscribers
- DDD domain: `events`, `workers`, `findings`, `security` policies
- Secure-by-design: MILS boundaries, A2A envelopes, mTLS metadata, scope/HITL middleware
- Kafka/Redpanda event bus (`USE_KAFKA`), worker daemons, router/critic/coordinator consumers
- MCP Tool Gateway (PEP), HITL L1/L2, DoW job budgets
- Secure RAG (`rag_query`), Skill Gateway (`load_skill`), K8s sandbox connector
- Prometheus metrics, Grafana dashboard, CI adversarial gates
- FastAPI: `POST /events`, `GET /status`, HITL resume API, `GET /metrics`
- Продуктовый слой `agents/` — personas, rules, routing plans, skills
- 100% unit test coverage gate on `cys_core/domain`

## Быстрый старт

```bash
uv sync

docker compose up -d   # Postgres + Redis + Redpanda + Qdrant

cp .env.example .env   # LLM API key

uv run cys-agi info

# Ingest SIEM event → enqueue SOC worker
uv run cys-agi ingest -t siem.alert -p '{"alert":"powershell encoded command"}' -s high

# Process queued worker job
uv run cys-agi worker --once

# Control plane status
uv run cys-agi status

# Manual investigation (all workers)
uv run cys-agi session -g "Assess CI/CD pipeline risks"

# HTTP API
uv run cys-agi serve --port 8080

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
| `session -g "..."` | Manual investigation (`manual.investigation` event) |
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
cys-agi/
├── agents/                 # Продукт: personas, rules, plans, skills
├── bootstrap/              # settings, DI container, product_loader
├── connectors/             # SIEM poll → ingress API
├── interfaces/             # Delivery: api, ingress, worker, control_plane, gateways, rag, cli
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
- API-ключ LLM-провайдера — для live worker runs

## Лицензия

MIT. См. [LICENSE](LICENSE).
