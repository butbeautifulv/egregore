# Архитектура egregore

> **Visual overview for architects:** [docs/architecture-site/](../../../docs/architecture-site/) — static site with UML diagrams (k3s offline: `https://<host>:30080`).

## Обзор

egregore — **event-driven** multi-agent SOC platform с тремя плоскостями:

1. **Ingress** (`interfaces/ingress/`, `interfaces/api/`) — приём structured events (CLI, FastAPI, webhooks, SIEM poll)
2. **Control plane** (`interfaces/control_plane/`, `cys_core/domain/events/`) — router, critic, coordinator, L2 HITL, escalation
3. **Worker plane** (`interfaces/worker/`, ephemeral sandbox) — автономные domain agents per event

Единый **AgentRuntime** + **AgentRegistry** для LLM worker runs. Все сценарии идут через **EventIngress** (batch LangGraph pipeline удалён).

Интерактивный путь (Operator UI): `ManageRun` → `RunStep` → тот же `AgentRuntime`.

### Слои (DDD)

| Слой | Путь | Ответственность |
|------|------|-----------------|
| Domain | `cys_core/domain/` | модели, security, routing rules, catalog, memory |
| Application | `cys_core/application/` | ports, use-cases, `ProfilePolicyResolver` |
| Infrastructure | `cys_core/infrastructure/` | Kafka, queue, sandbox, memory stores |
| Product load | `bootstrap/product_loader.py` | YAML personas → `AgentDefinition` |
| Registry | `cys_core/registry/` | `AgentRegistry`, tools, schemas |
| Runtime | `cys_core/runtime/` | `AgentRuntime` — только `AgentDefinition`, без имён persona |
| Delivery | `interfaces/` | FastAPI, workers, control, gateways, RAG |
| DI | `bootstrap/container.py` | wiring портов |

### Middleware stack (`AgentRuntime._build_middleware`)

1. `PromptContextMiddleware` — sanitizer + guardrails
2. `MemoryContextMiddleware` — episodic injection (при `investigation_id`)
3. `ContextSummaryMiddleware` — optional
4. `ScopeMiddleware` — tool allowlist per persona
5. `ToolCoercionMiddleware`
6. `SecurityMiddleware` — rate limit, anomaly, L1 HITL
7. `HumanInTheLoopMiddleware` — dangerous tools
8. SGR middleware **или** `OneToolPerTurnMiddleware`

Подробнее: [PLATFORM_TRUTH_MAP.md](PLATFORM_TRUTH_MAP.md).

## Data flow: event-driven + MAS memory

```
SIEM / NetFlow / Doc / Manual
         │
         ▼
   EventIngress.ingest() / RouterConsumer  ──► security.events.raw (Kafka)
         │
         │  DispatchEvent (shared use-case)
         ├── manual.investigation ──► PlanInvestigation (LLM planner)
         │                              └── sequential enqueue (depends_on_persona chain)
         └── other events ──► EventRouter (agents/plans/*.yaml, parallel fan-out)
         │
         ▼
   JobQueue.enqueue(WorkerJob)   # correlation_id = investigation_id
         │
         ▼
   WorkerOrchestrator.run_job()
         │
         ├── InvestigationStateStore + EpisodicMemoryStore (read prior findings)
         ├── SandboxConnector.create(run_id, persona)
         ├── AgentRuntime.arun(persona, payload, sandbox_tools)
         │      ├── Postgres checkpointer (thread: worker:{persona}:{job_id})
         │      ├── LangGraph store (namespace KV)
         │      ├── MemoryContextMiddleware (episodic injection)
         │      └── MCP Tool Gateway + load_skill
         ├── OutputGuardrails.validate_schema()
         ├── EpisodicMemoryStore.append(pending_finding, trust=0.3)
         ├── SecureAgentBus.send_message → bus_recipients + critic
         └── SandboxConnector.destroy(run_id)
         │
         ▼
   CriticService  — trust_score, L2 HITL, escalation, promote to finding, revision enqueue
   CoordinatorService  — LLM narrative from InvestigationState + memory
```

### Memory layers

| Layer | Store | Key | Purpose |
|-------|-------|-----|---------|
| Thread (short-term) | Postgres LangGraph checkpointer | `worker:{persona}:{job_id}` | HITL pause/resume within job |
| Job / HITL metadata | `worker_jobs` (Postgres) | `job_id` | Durable pause/resume across pod restart |
| Episodic (cross-session) | `agent_memory_entries` | `(tenant_id, investigation_id)` | `finding` (critic-approved) + `pending_finding` (pre-critic) |
| Investigation state | `investigation_states` | `(tenant_id, investigation_id)` | Plan, completed personas, summaries |
| Knowledge (RAG) | Qdrant (optional) | tenant ACL | Playbooks/runbooks — `USE_REAL_EMBEDDINGS` opt-in |

## Control plane (production)

| Daemon | Topic in | Output |
|--------|----------|--------|
| `uv run egregore router` | `security.events.raw` | worker job enqueue |
| `uv run egregore critic` | `bus.findings` (channel=critic) | awaiting_approval, escalation |
| `uv run egregore coordinator` | `bus.findings` (channel=coordinator) | narratives |

**L2 HITL:** critic `requires_hitl()` → `security.events.awaiting_approval`  
**Escalation:** critic-approved → `security.events.escalation` → `redteam-engagement` plan  
**Bus trust:** `soc→redteam` только через `escalation` + `critic_approved` (не direct `finding`)

## Роли агентов

Полный индекс: `agents/manifest.yaml` (15 workers + 2 control). Примеры:

### Workers (ephemeral)

| Persona | Event types | Bus recipients |
|---------|-------------|----------------|
| soc | `siem.alert`, `edr.alert`, `iam.event` | network, critic, coordinator |
| network | `netflow.beacon`, `dns.anomaly`, `escalation` | soc, critic |
| redteam | `escalation`, `manual.investigation` (high+) | critic, coordinator |
| compliance | `doc.upload`, `compliance.schedule` | critic, coordinator |

### Control (always on)

| Persona | Роль |
|---------|------|
| critic | Observer: trust_score, L2 HITL gate, escalation publisher |
| coordinator | Control tower: narratives для user |

## Security layers

| Layer | Component |
|-------|-----------|
| Ingress | InputSanitizer (`source=external`) |
| Tool PEP | `interfaces/gateways/tool/` — sanitize, audit, DoW chain depth |
| Skills | `interfaces/gateways/skill/` — hash verify, delimiters, allowlist |
| RAG | `interfaces/rag/` — ingest scan, ACL pre-filter, fail-closed `rag_query` |
| Worker | ScopeMiddleware, SecurityMiddleware (L1 HITL interrupt), job budgets |
| Bus | SecureAgentBus — HMAC, trust levels, escalation-only paths |
| Output | OutputGuardrails — schema, PII, exfiltration |
| Policy | `ProfilePolicyResolver` — catalog → env → defaults |

## Tooling & datasources

Отдельной domain-сущности «datasource» нет. Источники данных для агентов:

- **RAG** — `interfaces/rag/`, Qdrant, tenant ACL
- **Veil graph** — read-only MCP (`ti_*`, `playbook_*`)
- **SIEM** — `query_siem_readonly` tool
- **Veneno MCP** — HITL-gated exec tools (partial integration)

## Ports (`cys_core/application/ports/`)

| Port | Реализация |
|------|------------|
| `PersistenceConnector` | `cys_core/persistence.py` (`auto` \| `memory` \| `postgres`) |
| `JobStorePort` | `cys_core/infrastructure/job_store/` (Postgres \| InMemory) |
| `EpisodicMemoryStore` | `cys_core/infrastructure/memory/stores.py` |
| `ModelConnector` | `cys_core/llm/` |
| `SandboxConnector` | `cys_core/infrastructure/sandbox.py` (`local` \| `k8s`) |
| `JobQueueConnector` | `cys_core/infrastructure/queue.py` (Redis \| Kafka) |
| `AgentTransportConnector` | `cys_core/infrastructure/bus_transport.py` (Redis + subscriber \| Kafka) |

`bootstrap/container.py` — composition root.

## Observability

- **Prometheus:** `GET /metrics` on ingress API and tool gateway
- **OpenTelemetry:** worker/API spans → Tempo (`OTEL_ENABLED`, `cys_core/observability/otel*.py`)
- **Langfuse:** LLM traces + LLM-as-judge (`persona`, `job_id`, `correlation_id`)
- **Loki/Promtail:** structured JSON logs (k3s offline obs stack)
- **Grafana:** `deploy/observability/grafana/dashboards/egregore/`

Runbook: [OBSERVABILITY.md](OBSERVABILITY.md).

## Evals

- **Runtime:** trace critic (`evaluate_trace_critic.py`), Langfuse judge, critic trust_score
- **Batch adapters (stub):** RAGAS, tau2, BFCL in `application/evals/` — not wired to CI yet

## API (`interfaces/api/app.py`)

| Endpoint | Описание |
|----------|----------|
| `POST /events` | Ingest structured event |
| `GET /status`, `GET /status/stream` | Control plane snapshot + SSE |
| `GET /metrics` | Prometheus metrics |
| `GET /investigations`, `GET /investigations/{id}` | Investigation CRUD |
| `GET /jobs/{id}` | Job status (incl. `awaiting_approval`) |
| `GET /approvals/pending` | L1 HITL queue |
| `POST /jobs/{id}/resume` | Resume paused worker job |
| `POST /runs`, `POST /runs/{id}/steps` | Interactive runs (Operator UI) |
| `POST /workers/process-one` | Process next queued job |

## Plans = routing rules

`agents/plans/*.yaml` содержат `routing.rules`:

| Plan | Назначение |
|------|------------|
| `incident-triage` | SOC + network (default) |
| `compliance-audit` | Compliance worker |
| `redteam-engagement` | Redteam on escalation |
| `full-assessment` | Manual investigation — all workers |

## Зависимости

| Пакет | Роль |
|-------|------|
| `langchain` | `create_agent`, middleware |
| `langgraph` | Checkpointer, HITL interrupt |
| `litellm` | LLM provider |
| `fastapi` + `uvicorn` | Event/status API, tool gateway |
| `redis` | Job queue + bus (fallback) |
| `aiokafka` | Kafka transport |
| `qdrant-client` | RAG vector store (optional) |
| `prometheus-client` | Metrics |
| `opentelemetry-*` | OTEL traces (optional) |
