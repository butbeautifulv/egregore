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
5. При необходимости: schema в `cys_core/registry/schemas.py`, tool в `tools.py`
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

Следовать [docs/AI_Agent_Security_Cheat_Sheet.md](docs/AI_Agent_Security_Cheat_Sheet.md):

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
USE_MEMORY_FALLBACK=true STAGE=test pytest tests/ -q
```

- `tests/registry/` — загрузка personas, rules injection, runtime
- `tests/adversarial/` — prompt injection, exfiltration, tool abuse, bus chaining

## Язык

- Ответы агентов: **русский**
- JSON keys: **английский**
- Код и коммиты: английский

## Стиль кода

- KISS, DRY, SOLID
- Минимальный diff — не трогать несвязанный код
- Следовать существующим паттернам в `cys_core/`
- Комментарии только для неочевидной логики
