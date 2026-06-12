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

## Режимы работы

| STAGE | Persistence | Queue/Bus |
|-------|-------------|-----------|
| `test` | memory | in-memory fallback |
| `dev` | Postgres (fallback memory) | Redis or memory; Kafka if `USE_KAFKA=true` |
| `prod` | Postgres | Kafka (Redpanda) |

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
```

Manifests: `deploy/k8s/worker-job-template.yaml`, `deploy/k8s/networkpolicy.yaml`.  
Без K8s API client — fallback на local sandbox с префиксом `k8s-fallback-`.

## Secure Skills

- Metadata в `agents/manifest.yaml` + `agents/skills/*/SKILL.md`
- Body только через `load_skill` → `interfaces/gateways/skill/load.py` (hash + sanitize + delimiters)
- Allowlist per persona: `skills:` в `agent.yaml`
- Vetting внешних packs: [docs/SKILLS_VETTING.md](SKILLS_VETTING.md)

Первый gateway-backed tool: `query_siem_readonly` (SOC persona). Каждый invoke пишет audit record → `audit.tool.invocations` (Kafka) или in-memory (dev).

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

# Manual investigation (all workers)
uv run cys-agi session -g "Analyze workflow risks"

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
USE_QDRANT=true   # optional; in-memory fuzzy store when false
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
interfaces/ingress/router.py       # EventIngress
interfaces/worker/orchestrator.py # WorkerOrchestrator
interfaces/control_plane/                # CriticService, CoordinatorService, StatusStore
cys_core/domain/events/ # SecurityEvent, EventRouter
cys_core/infrastructure/# sandbox, queue, bus_transport
```

## Langfuse (опционально)

```bash
LANGFUSE_API_KEY=...
LANGFUSE_HOST=https://cloud.langfuse.com
```
