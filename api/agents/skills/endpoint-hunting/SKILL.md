---
name: endpoint-hunting
description: Endpoint hunting hypotheses, EDR queries, and persistence mechanism checks.
version: "1.0.0"
author: cys-agi
---

# Endpoint Hunting

## Scope
Endpoint hunting hypotheses, EDR queries, and persistence mechanism checks.

## Checklist
- Gather context from engagement goal and prior findings.
- Apply domain-specific heuristics; cite evidence for each claim.
- Flag uncertainty explicitly; do not invent IOCs or CVEs.

## Output format
Return structured JSON aligned with persona schema: concise `summary`, actionable fields, `confidence` 0–1.
