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
| `skills` | Product skills из `agents/skills/` |
| `hitl_tools` | Tools с human approval |
| `trust_level` | `untrusted` \| `internal` \| `privileged` \| `system` |
| `bus_recipients` | Allowed A2A message recipients |
| `language` | `ru` — ответы на русском |

## Kill-chain workers

| Persona | Role | Schema | ATT&CK focus |
|---------|------|--------|--------------|
| intel | worker | IntelFinding | Reconnaissance, Resource Development |
| hunter | worker | HunterFinding | Persistence, Defense Evasion, Discovery |
| identity | worker | IdentityFinding | Credential Access, Priv Esc, Lateral Movement |
| dfir | worker | DfirFinding | Collection, Impact, forensics |
| cloud | worker | CloudFinding | Cloud cross-tactic |
| purple | worker | PurpleFinding | Kill chain coverage / detection gaps |

## Core workers

| Persona | Role | Schema |
|---------|------|--------|
| redteam | worker | RedTeamFinding |
| network | worker | NetworkFinding |
| soc | worker | SocFinding |
| compliance | worker | ComplianceFinding |
| consultant | worker | ConsultantFinding |

## Control

| Persona | Role | Schema |
|---------|------|--------|
| critic | control | CriticResult |
| coordinator | control | — |
| planner | control | — |

## Workers vs control

- **Workers** запускаются эфемерно через `WorkerOrchestrator` на каждый event
- **Control** агенты — постоянные bus subscribers в `interfaces/control_plane/`, не sandbox workers

Все worker findings поддерживают kill-chain overlay: `attack_phase`, `mitre_tactics`, `mitre_techniques`.
