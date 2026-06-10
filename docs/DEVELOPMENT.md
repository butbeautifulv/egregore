# Разработка cys-agi

## Окружение

```bash
# Python 3.13+
uv sync

# Инфраструктура
docker compose up -d

# Конфиг
cp .env.example .env
```

### Docker services

| Service | Port | Credentials |
|---------|------|-------------|
| Postgres 16 | 5432 | `postgres` / `password`, DB `cys_agi` |
| Redis 7 | 6379 | password `password` |

## Режимы работы

| STAGE | Persistence | HITL |
|-------|-------------|------|
| `test` | always memory | auto-approve possible |
| `dev` | Postgres (fallback memory) | auto-approve if threshold ≥ medium |
| `prod` | Postgres | strict HITL |

Для локальной разработки без Docker:

```bash
USE_MEMORY_FALLBACK=true STAGE=dev python main.py assess -i "test input"
```

## CLI для отладки

```bash
# Конфигурация
python main.py info

# Один агент (быстрая проверка prompt/tools)
python main.py agent redteam
python main.py agent critic --input '[{"agent":"redteam","data":{}}]'

# Полный pipeline
python main.py assess -i "Authorized scope: test" --thread-id debug-001

# HITL resume
python main.py resume --thread-id debug-001 --approve

# Coordinator session
python main.py session -g "Analyze workflow risks" --thread-id sess-001
```

## Тестирование

```bash
# Все тесты
USE_MEMORY_FALLBACK=true STAGE=test uv run pytest tests/ -v

# Registry (personas, rules, runtime)
uv run pytest tests/registry/ -v

# Adversarial security
uv run pytest tests/adversarial/ -v

# Один тест
uv run pytest tests/registry/test_agent_registry.py::test_registry_loads_all_personas -v
```

`pyproject.toml` задаёт `pythonpath = ["."]` — PYTHONPATH вручную не нужен.

## Добавление persona

### 1. Структура папки

```
agents/personas/myagent/
├── agent.yaml
├── AGENT.md
└── samples/
    └── default.txt
```

### 2. agent.yaml

```yaml
name: myagent
description: Short description
role: specialist          # specialist | critic | coordinator
output_schema: MyFinding  # из schemas.py
tools:
  - read_repo_metadata
hitl_tools: {}            # tool_name: true для HITL
trust_level: internal       # untrusted | internal | privileged | system
bus_recipients:
  - critic
language: ru
sample: samples/default.txt
```

### 3. AGENT.md

Markdown system prompt. Опционально YAML frontmatter:

```markdown
---
title: My Agent
---

You are MyAgent. Analyze ...
```

### 4. Schema (если новая)

`cys_core/registry/schemas.py`:

```python
class MyFinding(BaseModel):
    severity: str
    summary: str
    ...
```

Зарегистрировать в `schema_registry`.

### 5. Tool (если новый)

`cys_core/registry/tools.py` — `@tool` function + register в `ToolRegistry`.

### 6. manifest.yaml

Добавить имя в `personas.specialists` (или critic/coordinator).

### 7. Тест

```bash
uv run pytest tests/registry/ -q
python main.py agent myagent
```

## Добавление rule

Файл `agents/rules/my-rule.md` — автоматически подхватывается `ProductContext` и добавляется ко всем system prompts.

## Добавление product skill

```
agents/skills/my-skill/SKILL.md
```

Frontmatter + domain knowledge. Coordinator загружает из `./agents/skills/`.

## Добавление plan

`agents/plans/my-plan.yaml` — описание stages и personas. Запись в `manifest.yaml` → `plans:`.

> Plan-driven dispatch в graph пока не реализован; план — контракт и документация playbook.

## LLM providers

LiteLLM model strings:

| Provider | Пример `LLM_MODEL` |
|----------|-------------------|
| Anthropic | `anthropic/claude-sonnet-4` |
| OpenAI | `gpt-4o` |
| Gemini | `gemini/gemini-2.0-flash` |
| OpenRouter | `openrouter/anthropic/claude-sonnet-4` + `LLM_BASE_URL` |

Ключ: соответствующая env var (`ANTHROPIC_API_KEY`, etc.).

## Langfuse tracing

```bash
LANGFUSE_API_KEY=pk-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

Callbacks подключаются в `AgentRuntime` через `get_langfuse_callbacks()`.

## Частые проблемы

| Проблема | Решение |
|----------|---------|
| `No module named 'cys_core'` | `uv run pytest` или `pythonpath` в pyproject |
| Postgres connection refused | `docker compose up -d` или `USE_MEMORY_FALLBACK=true` |
| Agent not found | Проверить `agents/personas/<name>/agent.yaml` |
| LiteLLM auth error | Проверить API key в `.env` |
| HITL interrupt | `python main.py resume --thread-id ID --approve` |

## Структура тестов

```
tests/
├── registry/
│   ├── test_agent_registry.py
│   ├── test_product_context.py
│   └── test_runtime.py
└── adversarial/
    ├── test_prompt_override.py
    ├── test_data_exfiltration.py
    ├── test_tool_misuse.py
    └── ...
```

Adversarial тесты не требуют LLM — проверяют security primitives напрямую.
