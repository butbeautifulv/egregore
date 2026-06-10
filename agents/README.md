# agents/ — продуктовый слой cys-agi

Отдельно от Cursor build-skills (`.agents/skills/`, в `.gitignore`).

```
agents/
├── manifest.yaml          # индекс personas, plans, skills
├── personas/              # определения агентов
│   ├── redteam/
│   │   ├── agent.yaml
│   │   ├── AGENT.md
│   │   └── samples/
│   └── ...
├── rules/                 # глобальные ограничения → в system prompt
├── plans/                 # playbooks оценки
└── skills/                # domain knowledge → Deep Agents on-demand
```

## personas/

Runtime-агенты. `AgentRegistry` сканирует `personas/*/agent.yaml`.

## rules/

`security.md`, `scope.md`, `output.md` — подмешиваются ко всем personas через `ProductContext`.

## plans/

YAML playbooks: `full-assessment`, `incident-triage`, `compliance-audit`.

## skills/

Продуктовые SKILL.md модули (CI/CD, beaconing, compliance). Coordinator загружает `./agents/skills/`.

## Добавить persona

1. `personas/<name>/` + `agent.yaml`, `AGENT.md`, `samples/default.txt`
2. При необходимости — schema/tool в `cys_core/registry/`
3. Запись в `manifest.yaml`
4. `pytest tests/registry/`
