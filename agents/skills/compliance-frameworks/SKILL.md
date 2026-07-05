---
name: compliance-frameworks
description: Map findings to common compliance frameworks (SOC2, ISO 27001, PCI-DSS) for advisory output.
version: "1.0.0"
author: cys-agi
---

# Compliance Frameworks

## Scope
Map findings to common compliance frameworks (SOC2, ISO 27001, PCI-DSS) for advisory output.

## Checklist
- Gather context from engagement goal and prior findings.
- Apply domain-specific heuristics; cite evidence for each claim.
- Flag uncertainty explicitly; do not invent IOCs or CVEs.

## Output format
Return structured JSON aligned with persona schema: concise `summary`, actionable fields, `confidence` 0–1.
