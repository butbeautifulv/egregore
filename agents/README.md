# agents/ — продуктовый слой cys-agi

Runtime-конфигурация платформы. Отдельно от Cursor build-skills (`.agents/skills/`, в `.gitignore`).

## Структура

```
agents/
├── manifest.yaml          # индекс personas, plans, skills
├── personas/              # определения агентов
│   ├── redteam/
│   │   ├── agent.yaml     # config: tools, schema, role, trust
│   │   ├── AGENT.md       # system prompt
│   │   └── samples/
│   │       └── default.txt
│   ├── network/
│   ├── soc/
│   ├── compliance/
│   ├── critic/
│   └── coordinator/
├── rules/                 # глобальные ограничения
│   ├── security.md
│   ├── scope.md
│   └── output.md
├── plans/                 # playbooks оценки
│   ├── full-assessment.yaml
│   ├── incident-triage.yaml
│   └── compliance-audit.yaml
└── skills/                # domain knowledge (on-demand)
    ├── ci-cd-threats/
    ├── network-beaconing/
    └── compliance-frameworks/
```

## Как это загружается

| Папка | Загрузчик | Куда попадает |
|-------|-----------|---------------|
| `personas/` | `AgentRegistry` | Runtime agents |
| `rules/` | `ProductContext` | System prompt всех personas |
| `plans/` | `manifest.yaml` | Контракт playbooks (future dispatch) |
| `skills/` | Deep Agents coordinator | On-demand domain knowledge |

## Personas

| Persona | Role | Фокус |
|---------|------|-------|
| redteam | specialist | CI/CD, SAST, offensive analysis |
| network | specialist | NetFlow, DNS, beaconing |
| soc | specialist | Alerts, triage, incident context |
| compliance | specialist | Frameworks, control gaps |
| critic | critic | Reconciliation, trust_score |
| coordinator | coordinator | Deep Agents session orchestration |

Подробнее: [personas/README.md](personas/README.md)

## Rules

Глобальные ограничения для всех агентов. Новый `.md` файл в `rules/` автоматически подмешивается в system prompt.

Подробнее: [rules/README.md](rules/README.md)

## Plans

YAML playbooks — какие personas и в каком порядке. Default: `full-assessment`.

Подробнее: [plans/README.md](plans/README.md)

## Skills

Продуктовые SKILL.md модули. Coordinator: `skills=["./agents/skills/"]`.

Подробнее: [skills/README.md](skills/README.md)

## Добавить persona

1. `personas/<name>/` — `agent.yaml`, `AGENT.md`, `samples/default.txt`
2. Schema/tool в `cys_core/registry/` при необходимости
3. Запись в `manifest.yaml`
4. `pytest tests/registry/`

## manifest.yaml

Единый индекс продукта. Версия, список personas, plans, skills. Читается `ProductContext`.
