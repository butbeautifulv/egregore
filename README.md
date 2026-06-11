# cys-agi

Secure async multi-agent cybersecurity assessment platform with DDD boundaries, LangGraph pipelines, Deep Agents coordination, and LiteLLM provider abstraction.

Платформа безопасных мульти-агентов для оценки кибербезопасности. Архитектура сочетает чистый **domain** слой (DDD), **async/await** runtime, **LangGraph pipeline** для детерминированных оценок и **Deep Agents coordinator** для длинных сессий.

## Возможности

- 6 config-driven агентов (redteam, network, soc, compliance, critic, coordinator)
- DDD domain layer: agents, assessment, findings, security policies
- Dependency inversion для storage: `PersistenceConnector` port + `auto|memory|postgres` connectors
- Secure-by-design deployment profile: MILS boundaries, A2A envelopes, mTLS identity, non-root hardened containers
- Async-ready runtime: `AgentRuntime.arun()`, `run_assessment_async()`, `run_session_async()`
- Provider-agnostic LLM через LiteLLM (Anthropic, OpenAI, Gemini, OpenRouter)
- Security layer: sanitization, guardrails, rate limiting, agent bus, HITL
- Продуктовый слой `agents/` — personas, rules, plans, skills
- 100% unit test coverage for platform modules

## Быстрый старт

```bash
# Зависимости
uv sync

# Инфраструктура (Postgres + Redis)
docker compose up -d

# Конфигурация
cp .env.example .env
# Укажите API-ключ провайдера (ANTHROPIC_API_KEY, OPENAI_API_KEY и т.д.)

# Проверка
python main.py info

# Полная оценка (LangGraph pipeline)
python main.py assess --input "Authorized scope: repo acme/webapp, read-only SAST"

# Один агент
python main.py agent redteam

# Длинная сессия (Deep Agents coordinator)
python main.py session --goal "Assess CI/CD pipeline risks in authorized repo"

# Тесты безопасности
USE_MEMORY_FALLBACK=true STAGE=test python main.py adversarial-test
```

## CLI

| Команда | Описание |
|---------|----------|
| `info` | Конфигурация и список агентов |
| `assess -i "..."` | LangGraph pipeline: specialists → critic → HITL → report |
| `session -g "..."` | Deep Agents coordinator с subagents |
| `agent <name>` | Запуск одного persona |
| `resume --thread-id ID --approve` | Продолжение после HITL interrupt |
| `adversarial-test` | Запуск `pytest tests/` |

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                         main.py (CLI)                        │
└──────────────┬──────────────────────────────┬───────────────┘
               │                              │
    ┌──────────▼──────────┐        ┌──────────▼──────────┐
    │  graph/workflow.py  │        │ coordinator/        │
    │  LangGraph pipeline │        │ deep_assessment.py  │
    └──────────┬──────────┘        └──────────┬──────────┘
               │                              │
               └──────────────┬───────────────┘
                              │
               ┌──────────────▼──────────────┐
               │   cys_core/runtime/agent.py │
               │   AgentRuntime / arun        │
               └──────────────┬──────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
 ┌──────▼──────┐    ┌─────────▼────────┐   ┌──────▼──────┐
 │ cys_core/   │    │ cys_core/        │   │ cys_core/   │
 │ domain/     │    │ llm/ (LiteLLM)   │   │ registry/   │
 └──────┬──────┘    └──────────────────┘   └─────────────┘
        │
 ┌──────▼──────────────────────────────────────┐
 │ agents/                                      │
 │  personas/  rules/  plans/  skills/          │
 └─────────────────────────────────────────────┘
```

Подробнее: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Структура репозитория

```
cys-agi/
├── agents/                 # Продуктовый слой (в git)
│   ├── manifest.yaml
│   ├── personas/           # agent.yaml + AGENT.md
│   ├── rules/              # глобальные ограничения
│   ├── plans/              # playbooks оценки
│   └── skills/             # domain knowledge
├── cys_core/               # Платформенный код
│   ├── domain/             # DDD: agents, assessment, findings, security
│   ├── llm/                # LiteLLM provider
│   ├── registry/           # AgentRegistry, tools, schemas
│   ├── runtime/            # AgentRuntime sync/async APIs
│   ├── security/           # compatibility exports + infra helpers
│   └── middleware/         # scope, security middleware
├── graph/                  # LangGraph pipeline
├── coordinator/            # Deep Agents sessions
├── docs/                   # Документация
├── tests/                  # registry + adversarial
├── main.py                 # CLI entrypoint
└── config.py               # Pydantic settings
```

## Два слоя «agents»

| Слой | Путь | В git | Назначение |
|------|------|-------|------------|
| **Продукт** | `agents/` | да | Personas, rules, plans, skills — runtime |
| **Разработка** | `.agents/skills/` | нет | LangChain/LangGraph/Cursor build skills |

Не смешивать эти слои. См. [agents/README.md](agents/README.md).

## Переменные окружения

| Переменная | Default | Описание |
|------------|---------|----------|
| `LLM_PROVIDER` | `litellm` | Провайдер LLM |
| `LLM_MODEL` | `anthropic/claude-sonnet-4` | Модель (LiteLLM format) |
| `LLM_BASE_URL` | — | Кастомный endpoint (OpenRouter и т.д.) |
| `AGENTS_ROOT` | `agents` | Корень продуктового слоя |
| `STAGE` | `dev` | `dev` / `test` / `prod` |
| `USE_MEMORY_FALLBACK` | `false` | In-memory checkpointer вместо Postgres |
| `HITL_AUTO_APPROVE_THRESHOLD` | `low` | Авто-approve в dev при `>= medium` |
| `TRUST_SCORE_THRESHOLD` | `0.5` | Порог critic для HITL |
| `MAX_TOOL_CALLS_PER_MINUTE` | `30` | Rate limit |
| `PERSISTENCE_CONNECTOR` | `auto` | Storage connector: `auto`, `memory`, `postgres` |

Полный список: [`.env.example`](.env.example)

## Тестирование

```bash
# Все тесты (in-memory persistence)
USE_MEMORY_FALLBACK=true STAGE=test uv run pytest tests/ -q

# Только registry
uv run pytest tests/registry/ -q

# Только adversarial
uv run pytest tests/adversarial/ -q
```

## Добавление агента

1. Создать `agents/personas/<name>/` с `agent.yaml`, `AGENT.md`, `samples/default.txt`
2. При необходимости — schema в `cys_core/registry/schemas.py`, tool в `tools.py`
3. Записать в `agents/manifest.yaml`
4. `pytest tests/registry/`

## Документация

| Файл | Содержание |
|------|------------|
| [AGENTS.md](AGENTS.md) | Правила для AI-ассистентов |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Архитектура и data flow |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Разработка и отладка |
| [docs/SECURE_DEPLOYMENT.md](docs/SECURE_DEPLOYMENT.md) | Secure deployment, MILS, A2A/mTLS, container hardening |
| [agents/README.md](agents/README.md) | Продуктовый слой |
| [docs/AI_Agent_Security_Cheat_Sheet.md](docs/AI_Agent_Security_Cheat_Sheet.md) | Security reference |

## Требования

- Python ≥ 3.13
- Docker (Postgres 16, Redis 7)
- API-ключ LLM-провайдера

## Лицензия

MIT. См. [LICENSE](LICENSE).
