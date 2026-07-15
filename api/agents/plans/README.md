# Plans

Event routing playbooks — определяют **какой worker** запускается на **какой event**.

## Формат

```yaml
id: incident-triage
name: Incident triage
description: SOC and network workers for active incidents

routing:
  rules:
    - event_types: [siem.alert, edr.alert]
      min_severity: low
      personas: [soc]
      notify_control: true
    - event_types: [netflow.beacon]
      personas: [network]
```

## Планы

| Plan | Use case |
|------|----------|
| `incident-triage.yaml` | SIEM/EDR → soc/hunter; IAM → identity; NetFlow → network (default) |
| `kill-chain-assessment.yaml` | TI, hunting, cloud, forensics, purple validation |
| `compliance-audit.yaml` | Documents, scheduled audits |
| `redteam-engagement.yaml` | High-severity escalations → redteam |
| `full-assessment.yaml` | Manual investigation → all 11 workers |
| `consultation.yaml` | Advisory requests → consultant |

Загрузка: `EventRouter.from_plans_dir(agents/plans/)`.

CLI `session -g "..."` отправляет `manual.investigation` event.

## Deferred patterns

**Tree of Thoughts (ToT) / Graph of Thoughts (GoT)** — intentionally not implemented.
Linear `todo_snapshot` + hierarchical spawn (`delegate_research`, `spawn_worker`) cover planning without exponential branch cost.

