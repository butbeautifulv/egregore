# AGENTS.md

Правила для AI-ассистентов в репозитории **cys-agi**.

## Два разных «agents»

| Слой | Путь | В git | Назначение |
|------|------|-------|------------|
| **Продукт** | `agents/` | да | Runtime: personas, rules, plans, skills |
| **Разработка** | `.agents/skills/` | нет | Cursor build skills (LangChain, LangGraph) |

**Не смешивать.** Продуктовые агенты — только в `agents/personas/`. Build skills — только в `.agents/skills/`.

## Продуктовый слой `agents/`

```
agents/
├── manifest.yaml       # индекс personas, plans, skills
├── personas/           # agent.yaml + AGENT.md + samples/
├── rules/              # security.md, scope.md, output.md
├── plans/              # routing rules (event_types → personas)
└── skills/             # domain SKILL.md → on-demand playbooks
```

### Roles

| Role | Примеры | Где используется |
|------|---------|------------------|
| `worker` | redteam, network, soc, compliance | Ephemeral sandbox runs via `WorkerOrchestrator` |
| `control` | critic, coordinator | Async bus subscribers в `control/` |

Legacy alias: `by_role("specialist")` → `by_workers()`.

### Добавить persona

1. `agents/personas/<name>/agent.yaml` — role, tools, schema, trust_level, bus_recipients
2. `agents/personas/<name>/AGENT.md` — system prompt
3. `agents/personas/<name>/samples/default.txt`
4. Routing rule в `agents/plans/*.yaml` (если event-driven)
5. Запись в `agents/manifest.yaml`
6. `pytest tests/registry/`

## Платформенный код

### Единые точки входа

- **Events:** `ingress/router.py` → `EventIngress`
- **Workers:** `workers/orchestrator.py` → `WorkerOrchestrator`
- **LLM:** `cys_core/llm` — LiteLLM only
- **Агенты:** `AgentRegistry` + `AgentRuntime`
- **Конфиг:** `config.settings`

### Не делать

- Не восстанавливать batch `assess` pipeline как primary path
- Не создавать `agents/*.py` Python-модули для personas
- Не коммитить `.env`, ключи, `.agents/`
- Не редактировать `.cursor/plans/` без явного запроса

### Security

- Injection/PII: `cys_core/domain/security/patterns/` (RU priority)
- Input sanitization на ingress и перед LLM
- Tool allowlist per agent (`agent.yaml`)
- HITL на dangerous tools (`run_active_scan`)
- Sandbox-scoped MCP tools (`mcp_tools.py`)
- SecureAgentBus с trust levels

## Архитектура (кратко)

```
Ingress → EventRouter → JobQueue → WorkerOrchestrator → Bus
                                              ↓
                                    Critic + Coordinator (control)
```

Подробнее: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Мастер-план (cloud / Cursor agents)

Исполнение production roadmap — по [docs/MASTER_PLAN_SECURE_PLATFORM.md](docs/MASTER_PLAN_SECURE_PLATFORM.md).

- **Master agent**: читает план, декомпозирует подфазы `P{x}.{y}.{z}` из §7
- **Subagents**: max **3 parallel**; 1 subagent = 1 подфаза; ≤5 файлов на PR (§12)
- **Старт**: batch 0 — `P1.1.1`, `P1.1.2`, `P1.1.3` (§12.9)
- **Не редактировать** `.cursor/plans/` — канон в `docs/MASTER_PLAN_SECURE_PLATFORM.md`

## Тесты

```bash
USE_MEMORY_FALLBACK=true STAGE=test uv run pytest tests/ -q
USE_MEMORY_FALLBACK=true STAGE=test uv run pytest tests/ --cov=cys_core/domain --cov-report=term-missing
```

Структура:

- `tests/domain/` — events, workers, security, findings
- `tests/workers/`, `tests/ingress/`, `tests/control/` — event-driven wiring
- `tests/middleware/` — LangChain middleware
- `tests/infrastructure/` — sandbox, queue, CLI
- `tests/adversarial/` — security abuse cases

Coverage gate: **100%** на `cys_core/domain`.

## Cursor Cloud specific instructions

**cys-agi** — CLI + optional FastAPI (`python main.py serve`).

### Команды

| Действие | Команда |
|----------|---------|
| Тесты | `USE_MEMORY_FALLBACK=true STAGE=test uv run pytest tests/ -q` |
| Smoke | `USE_MEMORY_FALLBACK=true STAGE=test uv run python main.py info` |
| Event flow | `uv run python main.py ingest -t siem.alert -p '{"alert":"test"}'` then `worker --once` |

Без API-ключа: `info`, `ingest` (enqueue), `status`, `pytest`.

Подробнее: [README.md](README.md), [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).
