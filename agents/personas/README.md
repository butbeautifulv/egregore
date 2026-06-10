# Personas

Определения runtime-агентов. Каждая папка — один агент.

## Формат

```
<persona>/
├── agent.yaml      # machine-readable config
├── AGENT.md        # system prompt (human-readable)
└── samples/
    └── default.txt # example input for CLI `agent <name>`
```

## agent.yaml fields

| Field | Описание |
|-------|----------|
| `name` | Уникальный идентификатор |
| `description` | Краткое описание |
| `role` | `specialist` \| `critic` \| `coordinator` |
| `output_schema` | Имя Pydantic schema из `cys_core/registry/schemas.py` |
| `tools` | Список tools из `ToolRegistry` |
| `hitl_tools` | Tools требующие human approval |
| `trust_level` | `untrusted` \| `internal` \| `privileged` \| `system` |
| `bus_recipients` | Кому агент может слать сообщения через SecureAgentBus |
| `language` | `ru` — ответы на русском |
| `sample` | Путь к default sample |

## Текущие personas

| Persona | Role | Schema |
|---------|------|--------|
| redteam | specialist | RedTeamFinding |
| network | specialist | NetworkFinding |
| soc | specialist | SocFinding |
| compliance | specialist | ComplianceFinding |
| critic | critic | CriticResult |
| coordinator | coordinator | — |

## AGENT.md

System prompt. Поддерживается YAML frontmatter (опционально). При загрузке:

1. Парсится body из AGENT.md
2. Добавляется language suffix (если `language: ru`)
3. Подмешиваются `agents/rules/*.md`

Legacy: `SKILL.md` тоже поддерживается, но предпочтителен `AGENT.md`.
