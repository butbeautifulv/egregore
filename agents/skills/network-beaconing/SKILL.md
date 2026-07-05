---
name: network-beaconing
description: Detect C2 beaconing, DNS tunneling, and anomalous egress from network telemetry.
version: "1.0.0"
author: cys-agi
---

# Network Beaconing

## Scope
Detect C2 beaconing, DNS tunneling, and anomalous egress from network telemetry.

## Checklist
- Gather context from engagement goal and prior findings.
- Apply domain-specific heuristics; cite evidence for each claim.
- Flag uncertainty explicitly; do not invent IOCs or CVEs.

## Output format
Return structured JSON aligned with persona schema: concise `summary`, actionable fields, `confidence` 0–1.
