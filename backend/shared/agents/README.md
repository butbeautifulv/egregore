# agents/ — продуктовый слой cys-agi

Runtime-конфигурация: personas, routing plans, rules, skills.

## Структура

```
agents/
├── manifest.yaml
├── personas/           # worker + control agents
├── rules/              # global constraints → system prompt
├── plans/              # event routing rules (event_types → personas)
└── skills/             # on-demand playbooks
```

## Как это загружается

| Папка | Загрузчик | Куда попадает |
|-------|-----------|---------------|
| `personas/` | `AgentRegistry` | Worker/control agent definitions |
| `rules/` | `ProductContext` | System prompt всех personas |
| `plans/` | `EventRouter.from_plans_dir()` | Event → persona dispatch |
| `skills/` | Deep Agents coordinator | On-demand domain knowledge |

## Personas

### Kill-chain workers

| Persona | Role | Фокус |
|---------|------|-------|
| intel | worker | OSINT, CTI, recon enrichment |
| hunter | worker | Proactive persistence/evasion hunting |
| identity | worker | AD/IAM credential and lateral movement |
| dfir | worker | Forensics, timelines, eradication |
| cloud | worker | Cloud audit, misconfig, exfil |
| purple | worker | Kill chain coverage, detection gaps |

### Core workers

| Persona | Role | Фокус |
|---------|------|-------|
| redteam | worker | CI/CD, SAST, authorized offensive analysis |
| network | worker | NetFlow, DNS, beaconing, C2 |
| soc | worker | SIEM alerts, triage, timeline |
| compliance | worker | Frameworks, evidence audit |
| consultant | worker | Advisory consultation |

### Control

| Persona | Role | Фокус |
|---------|------|-------|
| critic | control | Finding validation, trust_score |
| coordinator | control | Assessment orchestration, kill chain reports |
| planner | control | LLM investigation planning |

## Plans (routing)

| Plan | Event types | Personas |
|------|-------------|----------|
| `incident-triage` | siem.alert, edr.alert, iam.event | soc, hunter, identity, network |
| `kill-chain-assessment` | ti.feed, hunt.hypothesis, cloud.*, forensics | intel, hunter, identity, cloud, dfir, purple |
| `compliance-audit` | doc.upload, compliance.schedule | compliance |
| `redteam-engagement` | escalation (high+) | redteam |
| `full-assessment` | manual.investigation | all 11 workers |
| `consultation` | manual.consultation | consultant |

Default plan: `incident-triage` (см. `manifest.yaml`).

Подробнее: [plans/README.md](plans/README.md)

## Добавить persona

1. `personas/<name>/` — agent.yaml, AGENT.md, samples/
2. Routing rule в `plans/*.yaml`
3. Запись в `manifest.yaml`
4. Schema в `cys_core/domain/findings/models.py` (если worker)
5. `pytest tests/registry/`
