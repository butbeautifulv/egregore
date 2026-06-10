# Plans

Playbooks оценки — описывают **какие** personas задействовать и в каком порядке.

| Plan | Use case |
|------|----------|
| `full-assessment.yaml` | Полный LangGraph pipeline (default) |
| `incident-triage.yaml` | Активный инцидент: SOC + network |
| `compliance-audit.yaml` | Аудит контролей и политик |

CLI `assess` использует `full-assessment` по умолчанию; планы можно расширять для кастомных graph entrypoints.
