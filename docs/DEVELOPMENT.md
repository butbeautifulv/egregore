# Разработка cys-agi

## Окружение

```bash
uv sync --group dev
docker compose up -d
cp .env.example .env
```

| Service | Port | Credentials |
|---------|------|-------------|
| Postgres 16 | 5432 | `postgres` / `password`, DB `cys_agi` |
| Redis 7 | 6379 | password `password` |
| Redpanda (Kafka) | 19092 | no auth (dev single-node) |

### Kafka / Redpanda (event bus)

Redpanda поднимается вместе с `docker compose up -d`. Для локальной разработки с Kafka:

```bash
# .env
USE_KAFKA=true
KAFKA_BOOTSTRAP_SERVERS=localhost:19092

# Проверка брокера
docker compose exec redpanda rpk topic list
docker compose exec redpanda rpk topic create security.events.raw worker.jobs.soc bus.findings
```

Топики (production naming):

| Topic | Назначение |
|-------|------------|
| `security.events.raw` | Ingress → router consumer |
| `worker.jobs.{persona}` | Router → worker daemon |
| `bus.findings` | Worker findings → critic/coordinator |
| `worker.jobs.dlq` | Poison jobs |

Без `USE_KAFKA=true` очередь и bus остаются на Redis / in-memory fallback (совместимость с существующим flow).

## Keycloak OIDC (Ingress + Tool Gateway)

Опциональная JWT-аутентификация по образцу Veil ([`projects/veil/docs/deploy/auth-keycloak.md`](../../veil/docs/deploy/auth-keycloak.md)). **По умолчанию выключена** (`AUTH_ENABLED=0`).

| Variable | Default | Role |
|----------|---------|------|
| `AUTH_ENABLED` | `0` | Включить JWT на Ingress API и Tool Gateway |
| `RBAC_ENABLED` | `0` | Проверять realm/client roles в токене |
| `KEYCLOAK_ISSUER` | — | Realm issuer, напр. `https://keycloak.example/realms/cxado` |
| `KEYCLOAK_AUDIENCE` | — | Client ID (`egregore-api`); fallback на `KEYCLOAK_CLIENT_ID` |
| `KEYCLOAK_CLIENT_ID` | `egregore-api` | Для `resource_access.<client>.roles` |
| `RBAC_ROLE_INGRESS` | `egregore-ingress` | `POST /events`, SIEM connector |
| `RBAC_ROLE_OPERATOR` | `egregore-operator` | HITL: resume, approvals, `process-one` |
| `RBAC_ROLE_GATEWAY` | `egregore-gateway` | `POST /invoke` на tool gateway |
| `RBAC_ROLE_READER` | `egregore-reader` | `GET /status`, `GET /jobs/{id}` |
| `GATEWAY_ACCESS_TOKEN` | — | Static Bearer worker → gateway при `AUTH_ENABLED=1` |

Realm roles (Keycloak): `egregore-ingress`, `egregore-operator`, `egregore-gateway`, `egregore-reader`. Client: `egregore-api`.

Публичные эндпоинты без JWT: `GET /metrics` (Ingress), `GET /health` (gateway).

```bash
# .env
AUTH_ENABLED=1
RBAC_ENABLED=1
KEYCLOAK_ISSUER=https://keycloak.example/realms/cxado
KEYCLOAK_AUDIENCE=egregore-api

# Dev token (password grant — не для production)
TOKEN=$(curl -sS -X POST "$KEYCLOAK_ISSUER/protocol/openid-connect/token" \
  -d "client_id=egregore-api" \
  -d "client_secret=YOUR_SECRET" \
  -d "grant_type=password" \
  -d "username=user" \
  -d "password=pass" | jq -r .access_token)

curl -sS -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -X POST http://localhost:8080/events \
  -d '{"event_type":"siem.alert","payload":{"alert":"test"}}'

curl -sS -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -X POST http://localhost:8090/invoke \
  -d '{"tool_name":"dedup_alerts","args":{"alerts_text":"a"},"persona":"soc","sandbox_id":"sandbox-1"}'
```

Ответы: **401** — нет/невалидный токен; **403** — нет нужной роли при `RBAC_ENABLED=1`.

## Режимы работы

| STAGE | Persistence | Job store | Queue/Bus |
|-------|-------------|-----------|-----------|
| `test` | memory | in-memory | in-memory fallback |
| `dev` | Postgres (fallback memory) | Postgres or in-memory | Redis or memory; Kafka if `USE_KAFKA=true` |
| `prod` | Postgres (fail-closed) | Postgres (fail-closed) | Kafka (Redpanda) |

### Connectors и secrets

| Переменная | Значения | Назначение |
|------------|----------|------------|
| `PERSISTENCE_CONNECTOR` | `auto` \| `memory` \| `postgres` | LangGraph checkpointer + store |
| `JOB_STORE_CONNECTOR` | `auto` \| `memory` \| `postgres` | HITL pause/resume + job status |
| `USE_MEMORY_FALLBACK` | `true` \| `false` | Явный override silent fallback (dev/test) |
| `BUS_SIGNING_KEY` | string | HMAC для SecureAgentBus (обязателен в prod) |
| `SIEM_ADAPTER` | `mock` \| `http` | Tool `query_siem_readonly` |
| `SIEM_BASE_URL` | URL | HTTP SIEM при `SIEM_ADAPTER=http` |
| `USE_REAL_EMBEDDINGS` | `true` \| `false` | Litellm embeddings для Qdrant (opt-in) |

В `STAGE=prod` при недоступном Postgres без `USE_MEMORY_FALLBACK=true` старт падает с `PersistenceUnavailableError` (не silent fallback). Метрика: `cys_persistence_fallback_total`.

### Миграции БД

```bash
# Применить migrations/*.sql (schema_migrations tracking)
uv run cys-agi migrate

# Или вручную
psql $POSTGRES_URL -f migrations/001_memory_tables.sql
psql $POSTGRES_URL -f migrations/002_worker_jobs.sql
```

Локально без Docker:

```bash
USE_MEMORY_FALLBACK=true STAGE=dev uv run cys-agi ingest -t siem.alert -p '{"alert":"test"}'
USE_MEMORY_FALLBACK=true STAGE=dev uv run cys-agi worker --once
```

## MCP Tool Gateway

PEP для sandbox tool calls: `POST /invoke` → execute → sanitize → `RETRIEVED_TOOL_DATA` wrapper.

```bash
# .env
USE_TOOL_GATEWAY=true
TOOL_GATEWAY_URL=http://localhost:8090

uv run uvicorn interfaces.gateways.tool.server:create_app --factory --port 8090
```

Worker с `USE_TOOL_GATEWAY=true` резолвит tools через gateway (`sandbox_tools`), не напрямую из registry.

### HITL L1 (high-risk tools)

`SecurityMiddleware` в prod/test вызывает `interrupt()` вместо error → job `awaiting_approval`.

```bash
GET  /jobs/{id}              # status: running | awaiting_approval | ...
GET  /approvals/pending      # очередь pending tool calls
POST /jobs/{id}/resume       # {"decision":"approve|reject|edit","approval_id":"appr-..."}
```

Paused jobs → `worker.jobs.paused` (Kafka). Approvals → `audit.hitl.approvals`.

### DoW (Denial of Wallet)

Per-job budgets на `WorkerJob` (defaults по persona в `cys_core/domain/workers/budgets.py`):

| Persona | max_cost_usd | max_tokens |
|---------|--------------|------------|
| soc | $2 | 50k |
| redteam | $5 | 80k |

- `SecurityMiddleware` + `AgentRuntime` — tool-call / token / cost caps
- `interfaces/gateways/tool/policy.py` — max 3 sequential high-risk tools (config: `MAX_HIGH_RISK_TOOL_CHAIN_DEPTH`)

## Sandbox (K8s)

```bash
# .env
SANDBOX_CONNECTOR=k8s
K8S_NAMESPACE=cys-agi
K8S_WORKER_IMAGE=cys-agi-worker:latest
```

При `SANDBOX_CONNECTOR=k8s` connector пытается `load_incluster_config()` / `load_kube_config()` и создать `BatchV1Api`.  
Manifests: `deploy/k8s/worker-job-template.yaml`, `deploy/k8s/networkpolicy.yaml`.  
Без K8s API — fallback на local sandbox с префиксом `k8s-fallback-`.

## Secure Skills

- Metadata в `agents/manifest.yaml` + `agents/skills/*/SKILL.md`
- Body только через `load_skill` → `interfaces/gateways/skill/load.py` (hash + sanitize + delimiters)
- Allowlist per persona: `skills:` в `agent.yaml`
- Vetting внешних packs: [docs/SKILLS_VETTING.md](SKILLS_VETTING.md)

Первый gateway-backed tool: `query_siem_readonly` (SOC persona).  
`SIEM_ADAPTER=mock` — canned JSON (dev). `SIEM_ADAPTER=http` + `SIEM_BASE_URL` — `GET {base}/search?q=...`.  
Каждый invoke пишет audit record → `audit.tool.invocations` (Kafka) или in-memory (dev).

```bash
curl -X POST http://localhost:8090/invoke \
  -H 'Content-Type: application/json' \
  -d '{"tool_name":"query_siem_readonly","args":{"query":"powershell"},"persona":"soc","sandbox_id":"sandbox-1"}'
```

## SIEM poll connector

Лёгкий сервис без LLM: опрашивает SIEM HTTP API и шлёт нормализованные события в Ingress.

```bash
# SIEM mock/stub должен отдавать GET {siem_base_url}/alerts → {"results": [...]}
python -c "
import asyncio
from connectors.siem_poll import SiemPollClient

async def main():
    async with SiemPollClient(
        siem_base_url='http://localhost:9090',
        ingress_url='http://localhost:8080',
        ingress_token='YOUR_JWT',  # при AUTH_ENABLED=1; иначе api_key для dev
    ) as client:
        print(await client.poll_once())

asyncio.run(main())
"
```

Payload санитизируется (`source=external`) **до** `POST /events`; hard injection → alert отбрасывается.

## CLI для отладки

```bash
uv run cys-agi info

# Event-driven flow
uv run cys-agi ingest -t siem.alert -p '{"alert":"powershell"}' -s high
uv run cys-agi worker --once
uv run cys-agi status

# API
uv run cys-agi serve --port 8080
curl -X POST http://localhost:8080/events \
  -H 'Content-Type: application/json' \
  -d '{"event_type":"siem.alert","payload":{"alert":"test"}}'

# Manual investigation (LLM planner → sequential worker jobs)
uv run cys-agi session -g "Analyze workflow risks"

# DB migrations
uv run cys-agi migrate

# Single worker debug
uv run cys-agi agent soc
uv run cys-agi agent redteam -i "sample input"

# Kafka production daemons (USE_KAFKA=true)
uv run cys-agi router
uv run cys-agi worker --daemon --persona soc
uv run cys-agi critic
uv run cys-agi coordinator
```

### Secure RAG

```bash
USE_QDRANT=true          # optional; in-memory fuzzy store when false
USE_REAL_EMBEDDINGS=true # litellm embeddings (default: 8-dim hash stub)
# Ingest via rag.ingest.staging consumer or MemoryVectorStore in tests
# SOC tool: rag_query via tool gateway
```

### Observability

```bash
# Metrics on ingress + gateway
curl localhost:8080/metrics
uv run uvicorn interfaces.gateways.tool.server:create_app --factory --port 8090

# Grafana dashboard: deploy/grafana/dashboards/cys-agi.json
```

CI: `.github/workflows/adversarial-gate.yml` (abuse-case matrix), `agent-policy-gate.yml` (agent.yaml policy drift).  
Opt-in live Postgres: `.github/workflows/integration-postgres.yml` (`workflow_dispatch`).

## Тестирование

```bash
USE_MEMORY_FALLBACK=true STAGE=test uv run pytest tests/ -q --cov=cys_core/domain

uv run pytest tests/domain/events/ -v
uv run pytest tests/workers/ -v
uv run pytest tests/ingress/ -v
uv run pytest tests/interfaces/control_plane/ -v
uv run pytest tests/adversarial/ -v
```

## Добавление persona

### agent.yaml

```yaml
name: myagent
description: Short description
role: worker              # worker | control
output_schema: MyFinding
tools:
  - dedup_alerts
hitl_tools: {}
trust_level: internal
bus_recipients:
  - critic
  - coordinator
language: ru
sample: samples/default.txt
```

### Routing rule

Добавить в `agents/plans/<plan>.yaml`:

```yaml
routing:
  rules:
    - event_types: [my.event.type]
      personas: [myagent]
      notify_control: true
```

### manifest.yaml

Добавить в `personas.workers` или `personas.control`.

## Добавление event type

1. Добавить literal в `cys_core/domain/events/models.py` → `EventType`
2. Routing rule в plan YAML
3. Тест в `tests/domain/events/`

## Структура event-driven кода

```
interfaces/ingress/router.py              # EventIngress (sync)
interfaces/ingress/router_consumer.py     # Kafka router (shared DispatchEvent)
cys_core/application/use_cases/dispatch_event.py  # routing + planner fork
interfaces/worker/orchestrator.py         # WorkerOrchestrator (sequential enqueue, dependency gate)
interfaces/control_plane/                 # CriticService, CoordinatorService, JobStore
cys_core/domain/events/                   # SecurityEvent, EventRouter
cys_core/domain/memory/                   # episodic memory, investigation state
cys_core/infrastructure/job_store/        # Postgres/InMemory HITL durable state
cys_core/infrastructure/memory/         # episodic + investigation stores
cys_core/infrastructure/migrations/     # SQL migration runner
```

### Multi-pod bus (Redis)

Без `USE_KAFKA=true` worker публикует findings в Redis pub/sub. Critic daemon вызывает `RedisBusTransport.start_subscriber_loop(["critic"])`.  
Для production multi-pod рекомендуется `USE_KAFKA=true` (critic/coordinator читают `bus.findings`).

## Langfuse (опционально)

```bash
LANGFUSE_API_KEY=...
LANGFUSE_HOST=https://cloud.langfuse.com
```
