# AGENTS.md

Правила для AI-ассистентов в репозитории **cys-agi**.

## Важно: два разных «agents»

1. **Продукт** — [`agents/`](agents/):
   - `personas/` — agent.yaml + AGENT.md
   - `rules/` — global constraints
   - `plans/` — playbooks
   - `skills/` — product domain skills (не Cursor)
2. **Разработка** — `.agents/skills/` в `.gitignore` (LangChain/LangGraph build skills).

Не смешивать эти два слоя.

## Изменения в продукте

- Новый агент → `agents/personas/<name>/` + запись в `manifest.yaml`
- LLM только через `cys_core.llm.get_model()`
- Runtime — `cys_core.runtime.AgentRuntime`
- Security — [docs/AI_Agent_Security_Cheat_Sheet.md](docs/AI_Agent_Security_Cheat_Sheet.md)

## Тесты

```bash
USE_MEMORY_FALLBACK=true STAGE=test pytest tests/ -q
```
