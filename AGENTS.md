# AGENTS.md

Правила для AI-ассистентов в репозитории **egregore**.

## Три слоя rules / skills (DRY hub)

| Слой | Путь | Runtime? | Назначение |
|------|------|----------|------------|
| **Core rules** | `shared/agent-rules/core/` via meta [`.cursor/rules/`](../../.cursor/rules/) when using `cxado.code-workspace` | Нет | Открывать workspace, не `rules-link` в submodule |
| **Project overlay** | `.agents/rules/project-*.mdc` | Нет | egregore arch, pytest, security only |
| **Generic agent skills** | `shared/skills/agent/*` | Нет | `make skills-install` → `~/.cursor/skills/` |
| **Product skills** | `agents/skills/` | **Да** | Skill Gateway — thin overlay на hub |

`devsecops-ai-security` в cxado-skills — **CI/CD** skill scanning, не `ai-agent-security` runtime.

## Agent workflow (Cursor)

Follow `.agents/rules/core-*.mdc` (hub) + `project-workflow.mdc` + `project-security.mdc`.

Master plan: [docs/MASTER_PLAN_SECURE_PLATFORM.md](docs/MASTER_PLAN_SECURE_PLATFORM.md)

SGR (Schema-Guided Reasoning): [docs/integration/sgr-reasoning.md](docs/integration/sgr-reasoning.md) — pattern port only; **no** runtime imports from `refs/sgr-agent-core-main` (cxado meta root).

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

### Repo layout (`backend/{contracts,worker,api}/src/`)

Python backend is split into three independently installable packages (see
[docs/MICROSERVICES_SPLIT_PLAN.md](docs/MICROSERVICES_SPLIT_PLAN.md)) — nothing
except the queue message and Postgres rows may cross the api↔worker boundary:

- **`backend/contracts/`** (`egregore-contracts`) — domain models, port
  interfaces, generic infra (Postgres/Kafka/Redis, catalog, authz). No
  fastapi router code, no langchain/langgraph/deepagents/litellm.
- **`backend/worker/`** (`egregore-worker`) — agent-execution runtime
  (LangChain/LangGraph today, swappable later), Tool Gateway, control-plane
  daemons (critic/coordinator). Depends on `egregore-contracts` (editable
  path dep).
- **`backend/api/`** (`egregore-api`) — FastAPI ingress/CRUD, event routing,
  HITL resume over HTTP. Depends on `egregore-contracts` only — no
  langchain/langgraph/deepagents in this package's venv.

Import names are unchanged (`from cys_core...`) — each package installs its
own subset under that same namespace. ASGI entrypoint: `interfaces/api/app.py`
(in `backend/api/`). Operator UI is **`web_ui/`** (not `ui/`). Product seed
**`backend/agents/`** (sibling of the three packages, not nested in any one
of them). Docker/compose: **`deploy/`** (`Dockerfile.api`, `Dockerfile.worker`).
The transitional `backend/shared/` pre-split monolith has been deleted
(task #52's zero-fallback verification gate passed — contracts/worker/api
each build, import, and test fully independently with zero fallback).

**Deployment invariant — worker pool must include a catch-all instance.**
Job routing by persona is enforced client-side, not by the queue: Kafka's
`KafkaJobQueue` requeues (not drops) a job whose persona doesn't match a
given worker's `--persona` flag, and Redis's `RedisJobQueue` ignores persona
entirely (one shared list). Both `scripts/dev.sh` and
`deploy/docker-compose.dev.yml` start every worker replica with no
`--persona` (catch-all) today, which is why this works — it is not
guaranteed by the code. If workers are ever partitioned by persona (e.g.
for isolation/scaling), the pool **must** still include an instance with
`persona=""` or `persona="planner"`, or engagement/follow-up meta-planning
(`WorkerJob(persona="planner", work_kind="engagement_plan"|"follow_up_plan")`)
silently stalls forever with no error — the job just gets endlessly
requeued. Watch `cys_job_queue_persona_requeued_total{persona="planner"}`
for this failure mode. See docs/MICROSERVICES_SPLIT_PLAN.md §16.

### Единые точки входа

- **Events:** `interfaces/ingress/router.py` → `EventIngress`
- **Workers:** `interfaces/worker/orchestrator.py` → `WorkerOrchestrator`
- **CLI:** `cd backend/api && uv run egregore` (serve/ingest/session/migrate/info/router) or `cd backend/worker && uv run egregore` (worker/critic/coordinator/status/agent)
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

### Agent tooling (Cursor)

При исследовании кода: **scoped Grep/Read** в `projects/egregore/`; **Context7** — только для сторонних библиотек. См. meta [docs/agents/cursor-mcp-tooling.md](../../../docs/agents/cursor-mcp-tooling.md).

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

**Агентам: только батчами**, и **отдельно на каждый пакет** —
`cd backend/{contracts,worker,api} && ./scripts/pytest_batches.sh`, не
`uv run pytest` на весь `tests/` одним процессом. `backend/shared`
(транзитный монолит) удалён — три пакета полностью независимы.

- **Точечно** после правок: только затронутые батчи, в том пакете, где лежит
  правка (см. `.cursor/rules/project-egregore-pytest-batches.mdc`).
- **Полный прогон** — перед PR / после cross-cutting рефакторинга: все три
  пакета, не только тот, что менялся (контракт между ними — импорт-граф, а
  не файл; изменение в contracts может сломать worker/api).

Правило: `.cursor/rules/project-egregore-pytest-batches.mdc`.

```bash
for pkg in contracts worker api; do
  (cd backend/$pkg && ./scripts/pytest_batches.sh)
  make -C backend/$pkg verify-architecture   # import boundaries + lint-imports + tests/architecture
done
# cys_core/domain physically lives only in backend/contracts/src — worker and
# api install it as an editable path dependency, so the domain-gate coverage
# check can never find data under their own src/ tree. contracts-only:
make -C backend/contracts domain-gate        # 100% on domain/runs, domain/catalog, domain/observability
checkov -d deploy --framework helm,dockerfile --config-file .checkov.yaml --soft-fail \
  --output sarif --output-file-path reports/checkov.sarif  # IaC gate smoke (from repo root)
cd backend/contracts && ./scripts/pytest_batches.sh tests/domain tests/application   # выборочно
cd backend/contracts && USE_MEMORY_FALLBACK=true STAGE=test uv run pytest tests/domain/ -q --cov=src/cys_core/domain --cov-fail-under=100
```

Architecture debt inventory: [`docs/ARCHITECTURE_DEBT.md`](docs/ARCHITECTURE_DEBT.md). Regenerate table: `python3 scripts/arch_inventory.py`.

**CI gates** (all required on PR): `arch-gate`, `adversarial-gate`, `agent-policy-gate`, `security-shift-left` (Fabrica B1–B6). See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md#ci).

Структура (батчи `pytest_batches.sh`, каждый пакет — свой `tests/`):

- `tests/domain/` — domain entities, policies, observability types (в основном contracts)
- `tests/application/` — use cases (contracts + worker + api, по границе)
- `tests/api/` — FastAPI routes (api)
- `tests/architecture/` — import boundaries, hexagon gates (все три, копия `verify_import_boundaries.py` на пакет)
- `tests/bootstrap/` — container, product loader (все три; `bootstrap.container` — namespace-split, свой у worker/api)
- `tests/connectors/` — Langfuse, external connectors
- `tests/infrastructure/` — sandbox, queue, stores
- `tests/ingress/` — event ingress (api)
- `tests/observability/` — trace backends
- `tests/registry/` — agents, tools (registry.tools/mcp_tools — worker-only)
- `tests/adversarial/` — security abuse cases

Coverage gate: **100%** на `cys_core/domain` (в основном contracts).

## Cursor Cloud specific instructions

**egregore** — CLI + optional FastAPI (`cd backend/api && uv run egregore serve`).

### Команды

| Действие | Команда |
|----------|---------|
| Тесты | `cd backend/{contracts,worker,api} && ./scripts/pytest_batches.sh` (все три) |
| Smoke | `cd backend/api && USE_MEMORY_FALLBACK=true STAGE=test uv run egregore info` |
| Event flow | `cd backend/api && uv run egregore ingest -t siem.alert -p '{"alert":"test"}'` then `cd backend/worker && uv run egregore worker --once` |

Без API-ключа: `info`, `ingest` (enqueue), `status`, `pytest`.

Подробнее: [README.md](README.md), [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).
