# Архитектура cys-agi

## Обзор

cys-agi — **event-driven** multi-agent SOC platform с тремя плоскостями:

1. **Ingress** (`interfaces/ingress/`, `interfaces/api/`) — приём structured events (CLI, FastAPI, webhooks, SIEM poll)
2. **Control plane** (`interfaces/control_plane/`, `cys_core/domain/events/`) — router, critic, coordinator, L2 HITL, escalation
3. **Worker plane** (`interfaces/worker/`, ephemeral sandbox) — автономные domain agents per event

Единый **AgentRuntime** + **AgentRegistry** для LLM worker runs. Все сценарии идут через **EventIngress** (batch LangGraph pipeline удалён).

### Слои (после DDD-рефактора)

| Слой | Путь | Ответственность |
|------|------|-----------------|
| Domain | `cys_core/domain/` | модели, security, routing rules |
| Application | `cys_core/application/` | ports, use-cases |
| Infrastructure | `cys_core/infrastructure/` | Kafka, queue, sandbox |
| Product load | `bootstrap/product_loader.py` | YAML personas → `AgentDefinition` |
| Registry | `cys_core/registry/` | `AgentRegistry`, tools, schemas |
| Runtime | `cys_core/runtime/` | `AgentRuntime` — только `AgentDefinition`, без имён persona |
| Delivery | `interfaces/` + root shims | FastAPI, workers, control, gateways |
| DI | `bootstrap/container.py` | wiring портов |

## Data flow: event-driven

```
SIEM / NetFlow / Doc / Manual
         │
         ▼
   EventIngress.ingest()  ──► security.events.raw (Kafka, optional)
         │
         ▼
   EventRouter (agents/plans/*.yaml routing rules)
         │
         ▼
   JobQueue.enqueue(WorkerJob)   # Redis or worker.jobs.{persona} (Kafka)
         │
         ▼
   WorkerOrchestrator.run_job()
         │
         ├── SandboxConnector.create(run_id, persona)   # local | k8s
         ├── AgentRuntime.arun(persona, payload, sandbox_tools)
         │      └── MCP Tool Gateway (USE_TOOL_GATEWAY) + load_skill
         ├── OutputGuardrails.validate_schema()
         ├── SecureAgentBus.send_message(finding)
         ├── BusTransport.publish(critic, coordinator)  # bus.findings
         └── SandboxConnector.destroy(run_id)
         │
         ▼
   CriticService  — trust_score, L2 HITL, escalation events
   CoordinatorService  — user narrative
```

## Control plane (production)

| Daemon | Topic in | Output |
|--------|----------|--------|
| `uv run cys-agi router` | `security.events.raw` | worker job enqueue |
| `uv run cys-agi critic` | `bus.findings` (channel=critic) | awaiting_approval, escalation |
| `uv run cys-agi coordinator` | `bus.findings` (channel=coordinator) | narratives |

**L2 HITL:** critic `requires_hitl()` → `security.events.awaiting_approval`  
**Escalation:** critic-approved → `security.events.escalation` → `redteam-engagement` plan  
**Bus trust:** `soc→redteam` только через `escalation` + `critic_approved` (не direct `finding`)

## Роли агентов

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

## Ports (`cys_core/application/ports.py`)

| Port | Реализация |
|------|------------|
| `PersistenceConnector` | `cys_core/persistence.py` |
| `ModelConnector` | `cys_core/llm/` |
| `SandboxConnector` | `cys_core/infrastructure/sandbox.py` (`local` \| `k8s`) |
| `JobQueueConnector` | `cys_core/infrastructure/queue.py` (Redis \| Kafka) |
| `AgentTransportConnector` | `cys_core/infrastructure/bus_transport.py` (Redis \| Kafka) |

## Observability

- **Prometheus:** `GET /metrics` on ingress API and tool gateway (`cys_core/observability/`)
- **Langfuse:** trace tags per job (`persona`, `job_id`, `correlation_id`)
- **Grafana:** `deploy/grafana/dashboards/cys-agi.json`
- **CI gates:** `.github/workflows/adversarial-gate.yml`, `agent-policy-gate.yml`

## API (`interfaces/api/app.py`)

| Endpoint | Описание |
|----------|----------|
| `POST /events` | Ingest structured event |
| `GET /status` | Control plane snapshot |
| `GET /metrics` | Prometheus metrics |
| `GET /jobs/{id}` | Job status (incl. `awaiting_approval`) |
| `GET /approvals/pending` | L1 HITL queue |
| `POST /jobs/{id}/resume` | Resume paused worker job |
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
