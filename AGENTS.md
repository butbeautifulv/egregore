# AGENTS.md

Правила для AI-ассистентов в репозитории **egregore**.

## Три слоя rules / skills (DRY hub)

| Слой | Путь | Runtime? | Назначение |
|------|------|----------|------------|
| **Core rules** | `shared/agent-rules/core/` → `.agents/rules/core-*.mdc` | Нет | `make rules-link` — karpathy, critic, branches, kaizen, docs |
| **Project overlay** | `.agents/rules/project-*.mdc` | Нет | egregore arch, pytest, security only |
| **Generic agent skills** | `shared/skills/agent/*` | Нет | `make skills-install` → `~/.cursor/skills/` |
| **Product skills** | `agents/skills/` | **Да** | Skill Gateway — thin overlay на hub |

`devsecops-ai-security` в cxado-skills — **CI/CD** skill scanning, не `ai-agent-security` runtime.

## Agent workflow (Cursor)

Follow `.agents/rules/core-*.mdc` (hub) + `project-workflow.mdc` + `project-security.mdc`.

Master plan: [docs/MASTER_PLAN_SECURE_PLATFORM.md](docs/MASTER_PLAN_SECURE_PLATFORM.md)

## Два разных «agents» (историческая заметка)

| Слой | Путь | В git | Назначение |
|------|------|-------|------------|
| **Продукт** | `agents/` | да | Runtime: personas, rules, plans, skills |
| **Cursor dev** | `.agents/rules/` (core symlinks + overlay) | да | Workflow rules; skills via `make skills-install` |

**Не смешивать.** Продуктовые агенты — только в `agents/personas/`. Core rules — symlink из hub, не копировать.

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
- **CLI:** `uv run egregore`
- **Operator UI:** `ui/` — Next.js 16, HTTP client to FastAPI (`lib/api-client.ts`)
- **LLM:** `cys_core/llm` — LiteLLM only
- **Продукт → runtime:** `bootstrap/product_loader.py` → `AgentDefinition`
- **Агенты:** `AgentRegistry` + `AgentRuntime` (runtime не знает имён persona)
- **Конфиг:** `bootstrap/settings.py`
- **DI:** `bootstrap/container.py`

### Не делать

- Не восстанавливать batch `assess` pipeline как primary path
- Не создавать `agents/*.py` Python-модули для personas
- Не коммитить `.env`, ключи, `.agents/`, `ui/node_modules/`, `ui/.next/`
- Не редактировать `.cursor/plans/` без явного запроса
- Не подключать `shared/gui` как npm `file:` dependency в `ui/` — только vendor-copy ([`ui/docs/GUI_VENDOR.md`](ui/docs/GUI_VENDOR.md))

### Operator UI (`ui/`)

- Next.js App Router; shared primitives vendored in `ui/vendor/gui/`
- Sync from meta-repo: `cd ui && ./scripts/vendor-gui.sh && node scripts/rewrite-vendor-imports.mjs`
- UI changes: ≤5 files per PR (same rule as backend sub-phases)
- Dev: `make dev-ui` from repo root; see [ui/README.md](ui/README.md)

### Security

- Injection/PII: `cys_core/domain/security/patterns/` (RU priority)
- Input sanitization на ingress и перед LLM
- Tool allowlist per agent (`agent.yaml`)
- HITL на dangerous tools (`run_active_scan`)
- Sandbox-scoped MCP tools (`mcp_tools.py`)
- SecureAgentBus с trust levels
- **Keycloak OIDC** (optional): JWT Bearer на Ingress API (`interfaces/api/`) и MCP Tool Gateway (`interfaces/gateways/tool/`). Env: `AUTH_ENABLED`, `KEYCLOAK_ISSUER`, RBAC roles — см. [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md#keycloak-oidc-ingress--tool-gateway).

### MCP-first exploration (Cursor)

При исследовании кода предпочитать MCP перед blind grep:

1. **codebase-memory** — `search_code`, `trace_path`, `get_architecture`
2. **serena** — `find_symbol`, `find_referencing_symbols` (scope: `projects/egregore`)
3. Grep/read — только если MCP не дал ответа

После крупных структурных изменений — `index_repository` для egregore в codebase-memory.

### Langfuse observability (Cursor)

- Skill: `.cursor/skills/langfuse/` ([langfuse/skills](https://github.com/langfuse/skills)) — tracing setup, CLI, docs lookup
- Code: `cys_core/observability/langfuse_client.py`, `langfuse_tags.py`; LangChain `CallbackHandler` on all agent paths
- Dev stack: `make langfuse-dev-setup`, `make dev-langfuse-fresh`; runbook [docs/OBSERVABILITY.md](docs/OBSERVABILITY.md)

### LangChain / LangGraph skills (project)

Установлены в `.agents/skills/` (dev/build, не product runtime):

```bash
npx skills add langchain-ai/langchain-skills --skill '*' --yes
```

14 skills: `ecosystem-primer`, `langchain-fundamentals`, `langgraph-fundamentals`, `langgraph-persistence`, `langgraph-human-in-the-loop`, `deep-agents-*`, и др. Старт: **ecosystem-primer**.

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

**CI gates** (all required on PR): `arch-gate`, `adversarial-gate`, `agent-policy-gate`, `security-shift-left` (Fabrica B1–B6). See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md#ci).

Структура:

- `tests/domain/` — events, workers, security, findings
- `tests/workers/`, `tests/ingress/`, `tests/control/` — event-driven wiring
- `tests/middleware/` — LangChain middleware
- `tests/infrastructure/` — sandbox, queue, CLI
- `tests/adversarial/` — security abuse cases

Coverage gate: **100%** на `cys_core/domain`.

## Cursor Cloud specific instructions

**egregore** — CLI + optional FastAPI (`uv run egregore serve`).

### Команды

| Действие | Команда |
|----------|---------|
| Тесты | `./scripts/pytest_batches.sh` |
| Smoke | `USE_MEMORY_FALLBACK=true STAGE=test uv run egregore info` |
| Event flow | `uv run egregore ingest -t siem.alert -p '{"alert":"test"}'` then `uv run egregore worker --once` |

Без API-ключа: `info`, `ingest` (enqueue), `status`, `pytest`.

Подробнее: [README.md](README.md), [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).
