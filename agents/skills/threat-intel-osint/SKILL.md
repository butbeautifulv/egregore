---
name: threat-intel-osint
description: OSINT and threat intelligence collection for investigations and IOC enrichment.
version: "1.0.0"
author: cys-agi
---

# Threat Intel Osint

## Scope
OSINT and threat intelligence collection for investigations and IOC enrichment.

## Veil MCP (required for in-graph CTI)

Load `veil-knowledge` first, then use:

- `ti_search_in_category` — IOC/CVE/actor lookup in Veil graph (`category: ti` for IOCs, `vuln` for CVEs)
- `playbook_search` / `playbook_get` — procedure playbooks
- `playbook_for_technique` — MITRE-linked playbooks
- `enrich_ioc` — convenience alias; searches `category: ti`

## Checklist
- `load_skill("veil-knowledge")` when CTI or playbooks are needed.
- Gather context from engagement goal and prior findings.
- Apply domain-specific heuristics; cite evidence for each claim.
- Flag uncertainty explicitly; do not invent IOCs or CVEs.

## Output format
Return structured JSON aligned with persona schema: concise `summary`, actionable fields, `confidence` 0–1.
