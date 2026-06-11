# Архитектура cys-agi

## Обзор

cys-agi — гибридная платформа с DDD-границами и async-ready runtime:

1. **LangGraph pipeline** (`graph/`) — детерминированный flow для batch-оценок
2. **Deep Agents coordinator** (`coordinator/`) — длинные сессии с subagents и on-demand skills
3. **Domain layer** (`cys_core/domain/`) — чистые модели и политики без framework/I/O зависимостей

Оба пути используют единый **AgentRuntime** и **AgentRegistry**. Для async-сценариев доступны `AgentRuntime.arun()`, `run_assessment_async()` и `run_session_async()`.

## Dependency inversion и connectors

Application/interface слои не зависят от конкретного storage или model backend. Они используют ports из `cys_core/application/ports.py`:

- `PersistenceConnector` возвращает storage-agnostic `PersistenceContext` с `checkpointer` и `store`
- `ModelConnector` создаёт swappable chat model и callbacks
- `AgentTransportConnector` описывает A2A transport с обязательным mTLS flag

Конкретные реализации живут в infrastructure module `cys_core/persistence.py`:

| Connector | Назначение |
|-----------|------------|
| `auto` | Выбирает memory fallback для test/dev fallback, иначе пробует Postgres |
| `memory` | Всегда in-memory `MemorySaver` / `InMemoryStore` |
| `postgres` | Предпочитает Postgres saver/store |

Выбор connector: `PERSISTENCE_CONNECTOR=auto|memory|postgres`. Верхние слои (`runtime`, `graph`, `coordinator`) получают connector через factory и работают только с портом.

## Data flow: LangGraph assess

Assessment pipeline представлен как Directed Acyclic Graph (`graph/dag.py`) и валидируется перед компиляцией LangGraph.

```
START
  │
  ▼
ingest ── sanitize input, rate limit, reset state
  │
  ▼
dispatch ── Send() parallel to specialists
  │
  ├──► run_agent (redteam)
  ├──► run_agent (network)
  ├──► run_agent (soc)
  └──► run_agent (compliance)
  │
  ▼
critic ── reconcile findings, trust_score
  │
  ▼
hitl_gate ── interrupt() if high severity or low trust
  │
  ▼
report ── publish or reject
  │
  ▼
END
```

### Узлы (`graph/nodes.py`)

| Узел | Функция |
|------|---------|
| `ingest_node` | `InputSanitizer`, `RedisRateLimiter` |
| `dispatch_node` | `Send("run_agent")` для каждого `role=specialist` |
| `run_agent_node` | `await AgentRuntime.arun()` + `SecureAgentBus` |
| `critic_node` | Critic agent + `OutputGuardrails.validate_schema` |
| `hitl_gate_node` | `HitlPolicy` + `interrupt()` или auto-approve в dev |
| `report_node` | `AssessmentReportBuilder` |

Persistence: Postgres checkpointer (или `MemorySaver` в test/dev fallback).

## Data flow: Deep Agents session

```
User goal
  │
  ▼
coordinator (Deep Agent)
  ├── subagents: specialists + critic (from registry)
  ├── tools: run_assessment_pipeline, run_active_scan
  ├── skills: ./agents/skills/ (on-demand domain knowledge)
  └── interrupt_on: write_file, run_active_scan
```

Coordinator persona загружается из `agents/personas/coordinator/`.

## Registry и ProductContext

### AgentRegistry (`cys_core/registry/agents.py`)

Сканирует `agents/personas/*/agent.yaml`:

- Парсит `AGENT.md` (или legacy `SKILL.md`)
- Подмешивает `rules/*.md` через `ProductContext.augment_prompt()`
- Добавляет language suffix для `language: ru`

### ProductContext (`cys_core/registry/product_context.py`)

| Asset | Путь | Использование |
|-------|------|---------------|
| Manifest | `agents/manifest.yaml` | Индекс personas/plans/skills |
| Rules | `agents/rules/*.md` | Global constraints в system prompt |
| Plans | `agents/plans/*.yaml` | Playbooks (future: plan-driven dispatch) |
| Skills | `agents/skills/*/SKILL.md` | Deep Agents on-demand |

## AgentRuntime (`cys_core/runtime/agent.py`)

Единая точка создания агентов:

```python
create_agent(
    model=get_model(),           # LiteLLM
    tools=tool_registry.resolve(defn.tools),
    system_prompt=defn.system_prompt,
    middleware=[ScopeMiddleware, SecurityMiddleware, HITL?],
    response_format=schema_registry.get(defn.schema_name),
    checkpointer=...,
)
```

`run(name, input)` — sanitize → invoke → validate output schema.
`arun(name, input)` — async variant через `agent.ainvoke()`.

## Domain layer (`cys_core/domain/`)

| Bounded context | Содержание |
|-----------------|------------|
| `domain/agents` | `AgentConfig`, `AgentDefinition` |
| `domain/assessment` | `AssessmentState`, `HitlPolicy`, `AssessmentReportBuilder` |
| `domain/findings` | Finding schemas и `CriticResult` |
| `domain/security` | Risk policy, sanitizer, guardrails, agent bus, `SecurityViolation` |

Legacy paths (`cys_core/security/*`, `cys_core/schemas/findings.py`, `cys_core/registry/models.py`) оставлены как compatibility exports.

## LLM layer (`cys_core/llm/`)

- `ChatModelProvider` protocol
- `LiteLLMProvider` — единственная реализация
- Модель: `settings.llm_model` (формат LiteLLM: `anthropic/claude-sonnet-4`)
- Ключ: первый непустой из OPENROUTER, OPENAI, ANTHROPIC, GEMINI, AI_APIKEY

Нет прямой зависимости от `langchain-openai`.

## Security layer (`cys_core/security/`)

| Модуль | Назначение |
|--------|------------|
| `sanitizer.py` | Input sanitization (prompt injection patterns) |
| `guardrails.py` | Output validation, HITL triggers, `SecurityViolation` |
| `agent_bus.py` | Inter-agent messaging с trust levels |
| `rate_limit.py` | Redis/in-memory rate limiting |
| `risk.py` | Severity thresholds |
| `memory.py` | Memory poisoning protection |

Inter-agent messaging uses A2A envelopes (`a2a/1.0`) with signed payloads and mTLS identity metadata. Default identities are SPIFFE-style subjects: `spiffe://cys-agi/agent/<agent_id>`.

Middleware (`cys_core/middleware/`):

- `ScopeMiddleware` — tool allowlist enforcement
- `SecurityMiddleware` — per-call logging and guards

## Persistence (`cys_core/persistence.py`)

| Режим | Условие | Checkpointer | Store |
|-------|---------|--------------|-------|
| Memory | `USE_MEMORY_FALLBACK=true` или `STAGE=test` | `MemorySaver` | `InMemoryStore` |
| Postgres | default prod/dev | `PostgresSaver` | `PostgresStore` |
| Fallback | Postgres недоступен | auto → Memory | auto → InMemory |

## Tools и Schemas

- **Tools:** `cys_core/registry/tools.py` — `ToolRegistry`, stub implementations
- **Schemas:** `cys_core/registry/schemas.py` — Pydantic models для structured output

Agent yaml ссылается на tools и schema по имени:

```yaml
tools: [read_repo_metadata, parse_sast_report]
output_schema: RedTeamFinding
hitl_tools:
  run_active_scan: true
```

## Plans (roadmap)

`agents/plans/*.yaml` описывают playbooks. Сейчас CLI `assess` всегда запускает full pipeline (все specialists). Планы — контракт для будущего plan-driven dispatch.

## Зависимости

| Пакет | Роль |
|-------|------|
| `langgraph` | Assessment pipeline |
| `langchain` | `create_agent`, middleware |
| `deepagents` | Coordinator sessions |
| `litellm` | Provider-agnostic LLM |
| `redis` | Rate limiting |
| `psycopg` | Postgres checkpointer |
