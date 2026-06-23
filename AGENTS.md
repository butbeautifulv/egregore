# AGENTS.md

Правила для AI-ассистентов в репозитории **cys-agi**.

## Три слоя rules / skills (не смешивать)

| Слой | Путь | Runtime? | Назначение |
|------|------|----------|------------|
| **Product** | `agents/skills/` | **Да** | Skill Gateway — on-demand playbooks для workers |
| **Cursor stub** | `.agents/skills/` | Нет | Discovery stubs → `agents/skills/` |
| **cxado-skills** | `shared/skills/` (meta-repo) | Нет | Только devsecops + veil — **не** cys-agi product |

| **Agent rules** | `.agents/rules/cys-agi-*.mdc` | Нет | Cursor workflow: critic, karpathy, branches (паттерн Fish) |

`devsecops-ai-security` в cxado-skills — **CI/CD** skill scanning, не `ai-agent-security` runtime.

## Agent workflow (Cursor)

Follow `.agents/rules/cys-agi-*.mdc` — workflow, karpathy guidelines, critic, parallel branches, documentation, security, kaizen.

Master plan: [docs/MASTER_PLAN_SECURE_PLATFORM.md](docs/MASTER_PLAN_SECURE_PLATFORM.md)

## Два разных «agents» (историческая заметка)

| Слой | Путь | В git | Назначение |
|------|------|-------|------------|
| **Продукт** | `agents/` | да | Runtime: personas, rules, plans, skills |
| **Cursor dev** | `.agents/skills/` + `.agents/rules/` | да | Stubs и workflow rules для разработки в IDE |

**Не смешивать.** Продуктовые агенты — только в `agents/personas/`. Cursor stubs — только перенаправление на canonical `agents/skills/`.

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
| `control` | critic, coordinator | Async bus subscribers в `interfaces/control_plane/` |

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

- **Events:** `interfaces/ingress/router.py` → `EventIngress`
- **Workers:** `interfaces/worker/orchestrator.py` → `WorkerOrchestrator`
- **CLI:** `uv run cys-agi`
- **LLM:** `cys_core/llm` — LiteLLM only
- **Продукт → runtime:** `bootstrap/product_loader.py` → `AgentDefinition`
- **Агенты:** `AgentRegistry` + `AgentRuntime` (runtime не знает имён persona)
- **Конфиг:** `bootstrap/settings.py`
- **DI:** `bootstrap/container.py`

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
./scripts/pytest_batches.sh
./scripts/pytest_batches.sh --cov --domain-gate
USE_MEMORY_FALLBACK=true STAGE=test uv run pytest tests/domain/ -q --cov=cys_core/domain --cov-fail-under=100
```

Структура:

- `tests/domain/` — events, workers, security, findings
- `tests/workers/`, `tests/ingress/`, `tests/control/` — event-driven wiring
- `tests/middleware/` — LangChain middleware
- `tests/infrastructure/` — sandbox, queue, CLI
- `tests/adversarial/` — security abuse cases

Coverage gate: **100%** на `cys_core/domain`.

## Cursor Cloud specific instructions

**cys-agi** — CLI + optional FastAPI (`uv run cys-agi serve`).

### Команды

| Действие | Команда |
|----------|---------|
| Тесты | `./scripts/pytest_batches.sh` |
| Smoke | `USE_MEMORY_FALLBACK=true STAGE=test uv run cys-agi info` |
| Event flow | `uv run cys-agi ingest -t siem.alert -p '{"alert":"test"}'` then `uv run cys-agi worker --once` |

Без API-ключа: `info`, `ingest` (enqueue), `status`, `pytest`.

Подробнее: [README.md](README.md), [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).
