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

SGR (Schema-Guided Reasoning): [docs/integration/sgr-reasoning.md](docs/integration/sgr-reasoning.md) — pattern port only; **no** runtime imports from `shared/references/sgr-agent-core-main`.

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

### Repo layout (`src/`)

Python backend packages live under **`src/`** (`src/cys_core`, `src/interfaces`, `src/bootstrap`, `src/connectors`, `src/authz`). Import names are unchanged (`from cys_core...`). Operator UI is **`web_ui/`** (not `ui/`). Seed **`agents/`** stays at repo root.

### Единые точки входа

- **Events:** `interfaces/ingress/router.py` → `EventIngress`
- **Workers:** `interfaces/worker/orchestrator.py` → `WorkerOrchestrator`
- **CLI:** `uv run egregore`
- **Operator UI:** `web_ui/` — Next.js 16, HTTP client to FastAPI (`lib/api-client.ts`)
- **Operator TUI:** `tui/` — Go Bubble Tea, порт того же контракта (`internal/api/`)
- **Контракт UI+TUI:** [docs/operator-console-contract.md](docs/operator-console-contract.md)
- **LLM:** `cys_core/llm` — LiteLLM only
- **Продукт → runtime:** `bootstrap/product_loader.py` → `AgentDefinition`
- **Агенты:** `AgentRegistry` + `AgentRuntime` (runtime не знает имён persona)
- **Конфиг:** `bootstrap/settings.py`
- **DI:** `bootstrap/container.py`

### Не делать

- Не восстанавливать batch `assess` pipeline как primary path
- Не создавать `agents/*.py` Python-модули для personas
- Не коммитить `.env`, ключи, `.agents/`, `web_ui/node_modules/`, `web_ui/.next/`
- Не редактировать `.cursor/plans/` без явного запроса
- Не подключать `shared/gui` как `file:` dependency в `web_ui/` — только vendor-copy ([`web_ui/docs/GUI_VENDOR.md`](web_ui/docs/GUI_VENDOR.md))

### Operator UI (`web_ui/`)

- Next.js App Router; shared primitives vendored in `ui/vendor/gui/`
- Sync from meta-repo: `cd web_ui && ./scripts/vendor-gui.sh && node scripts/rewrite-vendor-imports.mjs`
- UI changes: ≤5 files per PR (same rule as backend sub-phases)
- Dev: `make dev-web-ui` from repo root; see [web_ui/README.md](ui/README.md)

### Security

- **Prompt layers:** persona (`persona_prompt`, mutable) + `GLOBAL_RULES` / `SECURITY_RULES` (immutable backend via `system_prompt_assembler.py`). See [ADR-004](docs/adr/ADR-004-immutable-prompt-rules.md).
- Injection/PII: `cys_core/domain/security/patterns/` (RU priority)
- Input sanitization на ingress и перед LLM
- Tool allowlist per agent (`agent.yaml`)
- HITL на dangerous tools (`run_active_scan`)
- Sandbox-scoped MCP tools (`mcp_tools.py`)
- **Veil MCP** (`VEIL_MCP_*`): graph + playbooks — [docs/integration/egregore-veil-mcp.md](../../docs/integration/egregore-veil-mcp.md)
- **MaxPatrol SIEM MCP** (`SIEM_MCP_*`): SOC incidents/events — [docs/integration/egregore-siem-mcp.md](../../docs/integration/egregore-siem-mcp.md); `make cxado-up-siem-mcp`
- **Nessus MCP** (`NESSUS_MCP_*`): vulnerability inventory — [docs/integration/egregore-tenable-mcp.md](../../docs/integration/egregore-tenable-mcp.md); `make cxado-up-tenable-mcp`
- SecureAgentBus с trust levels
- **Keycloak OIDC** (optional): JWT Bearer на Ingress API (`interfaces/api/`) и MCP Tool Gateway (`interfaces/gateways/tool/`). Env: `AUTH_ENABLED`, `KEYCLOAK_ISSUER`, RBAC roles — см. [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md#keycloak-oidc-ingress--tool-gateway).
- **Workspace + OpenFGA ReBAC** (ADR-005): workspaces, tenant bind, FGA `AUTHZ_MODE` — см. [docs/auth/oidc-openfga.md](docs/auth/oidc-openfga.md) и [docs/adr/ADR-005-workspace-oidc-openfga.md](docs/adr/ADR-005-workspace-oidc-openfga.md).

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
Operator API (/v1/work-orders, follow-ups)
        ↓
StartWorkOrder → StartEngagement → EventRouter → JobQueue
        ↓                                    ↓
  PlanFollowUpRunner              WorkerOrchestrator → RunWorkerJob
  (application/planning/)              ↓
                                 result_validator → finding_publisher
                                              ↓
                         Bus (workers only; control personas skip publish)
                                              ↓
                                    Critic + Coordinator (control)
```

- **Operator SSOT:** [docs/operator-console-contract.md](docs/operator-console-contract.md) — work orders, follow-up SSE, chat routing.
- **Bus policy:** control personas (`planner`, `critic`, `coordinator`) must not publish findings to `critic` via `WorkerFindingPublisher`; planner has empty `bus_recipients`.

Подробнее: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

**Visual architecture site** (for designers/architects): [docs/architecture-site/](../../docs/architecture-site/) in meta-repo · k3s offline `https://<host>:30080`

## Мастер-план (cloud / Cursor agents)

Исполнение production roadmap — по [docs/MASTER_PLAN_SECURE_PLATFORM.md](docs/MASTER_PLAN_SECURE_PLATFORM.md).

- **Master agent**: читает план, декомпозирует подфазы `P{x}.{y}.{z}` из §7
- **Subagents**: max **3 parallel**; 1 subagent = 1 подфаза; ≤5 файлов на PR (§12)
- **Старт**: batch 0 — `P1.1.1`, `P1.1.2`, `P1.1.3` (§12.9)
- **Не редактировать** `.cursor/plans/` — канон в `docs/MASTER_PLAN_SECURE_PLATFORM.md`

## Тесты

**Агентам: только батчами** — `./scripts/pytest_batches.sh`, не `uv run pytest` на весь `tests/` одним процессом.

- **Точечно** после правок: только затронутые батчи (см. `.cursor/rules/project-egregore-pytest-batches.mdc`).
- **Полный прогон** — перед PR / после cross-cutting рефакторинга.

Правило: `.cursor/rules/project-egregore-pytest-batches.mdc`.

```bash
./scripts/pytest_batches.sh
./scripts/pytest_batches.sh --cov --domain-gate
make -C projects/egregore domain-gate           # 100% on domain/runs, domain/catalog, domain/observability
make -C projects/egregore verify-architecture  # import boundaries + lint-imports + tests/architecture
./scripts/pytest_batches.sh tests/domain tests/application   # выборочно
USE_MEMORY_FALLBACK=true STAGE=test uv run pytest tests/domain/ -q --cov=src/cys_core/domain --cov-fail-under=100
```

Architecture debt inventory: [`docs/ARCHITECTURE_DEBT.md`](docs/ARCHITECTURE_DEBT.md). Regenerate table: `python3 scripts/arch_inventory.py`.

**CI gates** (all required on PR): `arch-gate`, `adversarial-gate`, `agent-policy-gate`, `security-shift-left` (Fabrica B1–B6). See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md#ci).

Структура (батчи `pytest_batches.sh`):

- `tests/domain/` — domain entities, policies, observability types
- `tests/application/` — use cases
- `tests/api/` — FastAPI routes
- `tests/architecture/` — import boundaries, hexagon gates
- `tests/bootstrap/` — container, product loader
- `tests/connectors/` — Langfuse, external connectors
- `tests/infrastructure/` — sandbox, queue, stores
- `tests/ingress/` — event ingress
- `tests/observability/` — trace backends
- `tests/registry/` — agents, tools
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
