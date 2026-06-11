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
├── rules/              # security.md, scope.md, output.md → system prompt
├── plans/              # YAML playbooks (full-assessment, incident-triage, …)
└── skills/             # domain SKILL.md → Deep Agents on-demand
```

### Добавить persona

1. `agents/personas/<name>/agent.yaml` — name, role, tools, schema, trust_level
2. `agents/personas/<name>/AGENT.md` — system prompt (можно YAML frontmatter)
3. `agents/personas/<name>/samples/default.txt` — пример входа
4. Запись в `agents/manifest.yaml`
5. При необходимости: schema в `cys_core/domain/findings/models.py` + регистрация в `registry/schemas.py`, tool в `tools.py`
6. `pytest tests/registry/`

### Roles

| Role | Примеры | Где используется |
|------|---------|------------------|
| `specialist` | redteam, network, soc, compliance | LangGraph parallel dispatch |
| `critic` | critic | LangGraph reconciliation |
| `coordinator` | coordinator | Deep Agents session |

## Платформенный код

### Единые точки входа

- **LLM:** `from cys_core.llm import get_model` — только через LiteLLM adapter
- **Агенты:** `AgentRegistry` + `AgentRuntime` — не создавать `create_agent()` напрямую в graph/coordinator
- **Конфиг:** `config.settings` — не хардкодить пути и ключи

### Не делать

- Не добавлять `langchain-openai` или прямые SDK вызовы
- Не создавать `agents/*.py` Python-модули для personas
- Не класть продуктовый контент в `.agents/skills/`
- Не редактировать `.cursor/plans/` без явного запроса
- Не коммитить `.env`, ключи, `.agents/`

### Security

Следовать [docs/reference/AI_Agent_Security_Cheat_Sheet.md](docs/reference/AI_Agent_Security_Cheat_Sheet.md) и [docs/reference/LLM_Prompt_Injection_Prevention_Cheat_Sheet.md](docs/reference/LLM_Prompt_Injection_Prevention_Cheat_Sheet.md):

- **Не читать** `docs/injections/` (локальный jailbreak-корпус) без явного запроса; не копировать payloads в код/тесты
- Injection/PII паттерны: `cys_core/domain/security/patterns/` (RU приоритет)
- Input sanitization перед LLM
- Tool allowlist per agent (`agent.yaml`)
- HITL для опасных tools (`run_active_scan`, `write_file`)
- Output schema validation
- Agent bus с trust levels

## Архитектура (кратко)

```
CLI → graph/workflow.py (LangGraph)  ─┐
    → coordinator/deep_assessment.py  ─┤→ AgentRuntime → LiteLLM
                                       │
agents/personas/ + rules/ ← AgentRegistry ← ProductContext
```

Подробнее: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Тесты

```bash
USE_MEMORY_FALLBACK=true STAGE=test uv run pytest tests/ -q
USE_MEMORY_FALLBACK=true STAGE=test uv run pytest tests/ --cov=cys_core/domain --cov-report=term-missing
```

Структура:

- `tests/domain/` — unit-тесты domain-политик (sanitizer, scope, hitl, findings)
- `tests/middleware/` — LangChain middleware adapters
- `tests/infrastructure/` — persistence, llm, rate_limit, memory, monitor
- `tests/graph/`, `tests/coordinator/` — orchestration wiring
- `tests/registry/` — smoke против реального `agents/`
- `tests/adversarial/` — security abuse scenarios

Coverage gate: **100%** на `cys_core/domain` (`pyproject.toml`).

Импорты: `cys_core.domain.*` для политик; `cys_core.security.*` только infrastructure (`monitor`, `memory`, `rate_limit`).

## Язык

- Ответы агентов: **русский**
- JSON keys: **английский**
- Код и коммиты: английский

## Стиль кода

- KISS, DRY, SOLID
- Минимальный diff — не трогать несвязанный код
- Следовать существующим паттернам в `cys_core/`
- Комментарии только для неочевидной логики

## Cursor Cloud specific instructions

**cys-agi** — CLI-приложение (нет web UI, нет отдельного API-сервера). Единственный runtime: `python main.py` / `uv run python main.py`.

### Зависимости и Python

- Менеджер пакетов: **uv** (`uv sync`). Lockfile: `uv.lock`, Python **≥ 3.13** (`.python-version`).
- `uv` обычно в `~/.local/bin`; при «command not found» добавить в PATH или переустановить: `curl -LsSf https://astral.sh/uv/install.sh | sh`.
- После `uv sync` использовать `uv run …` или активировать `.venv`.

### Инфраструктура (опционально)

| Сервис | Когда нужен | Без Docker |
|--------|-------------|------------|
| Postgres 16 | HITL resume, persistence в `dev`/`prod` | `USE_MEMORY_FALLBACK=true` |
| Redis 7 | Distributed rate limiting | In-memory fallback автоматически |

`docker compose up -d` поднимает только Postgres + Redis ([docker-compose.yml](docker-compose.yml)). В Cloud VM Docker может отсутствовать — для разработки и тестов достаточно memory fallback.

### Конфиг

```bash
cp .env.example .env   # LLM API key для live assess/session/agent
```

Без API-ключа работают: `info`, `adversarial-test`, `pytest`, загрузка registry и компиляция LangGraph.

### Команды (стандартные)

| Действие | Команда |
|----------|---------|
| Тесты | `USE_MEMORY_FALLBACK=true STAGE=test uv run pytest tests/ -q` |
| Smoke | `USE_MEMORY_FALLBACK=true STAGE=dev uv run python main.py info` |
| Live pipeline | `uv run python main.py assess -i "Authorized scope: …"` (нужен LLM key) |

Подробнее: [README.md](README.md), [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

### Линт

Отдельного linter (ruff/mypy) в репозитории нет; quality gate — pytest (102 теста, 100% coverage на `cys_core/domain`).
