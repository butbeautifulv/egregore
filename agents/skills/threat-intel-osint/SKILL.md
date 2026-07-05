---
name: threat-intel-osint
description: OSINT and threat intelligence collection for investigations and IOC enrichment.
version: "1.0.0"
author: cys-agi
---

# Threat Intel Osint

## Scope
OSINT and threat intelligence collection for investigations and IOC enrichment.

## Checklist
- Gather context from engagement goal and prior findings.
- Apply domain-specific heuristics; cite evidence for each claim.
- Flag uncertainty explicitly; do not invent IOCs or CVEs.

## Output format
Return structured JSON aligned with persona schema: concise `summary`, actionable fields, `confidence` 0–1.
