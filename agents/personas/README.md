# Personas

Определения runtime-агентов. Каждая папка — один агент.

## Формат

```
<persona>/
├── agent.yaml
├── AGENT.md
└── samples/default.txt
```

## agent.yaml fields

| Field | Описание |
|-------|----------|
| `name` | Уникальный идентификатор |
| `role` | `worker` \| `control` |
| `output_schema` | Schema из `cys_core/domain/findings/models.py` |
| `tools` | Tools из `ToolRegistry` |
| `hitl_tools` | Tools с human approval |
| `trust_level` | `untrusted` \| `internal` \| `privileged` \| `system` |
| `bus_recipients` | Allowed A2A message recipients |
| `language` | `ru` — ответы на русском |

## Текущие personas

| Persona | Role | Schema |
|---------|------|--------|
| redteam | worker | RedTeamFinding |
| network | worker | NetworkFinding |
| soc | worker | SocFinding |
| compliance | worker | ComplianceFinding |
| critic | control | CriticResult |
| coordinator | control | — |

## Workers vs control

- **Workers** запускаются эфемерно через `WorkerOrchestrator` на каждый event
- **Control** агенты — постоянные bus subscribers в `interfaces/control_plane/`, не sandbox workers
