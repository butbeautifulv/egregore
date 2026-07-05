---
name: ci-cd-threats
description: CI/CD pipeline threat modeling: secrets in logs, poisoned dependencies, and build integrity.
version: "1.0.0"
author: cys-agi
---

# Ci Cd Threats

## Scope
CI/CD pipeline threat modeling: secrets in logs, poisoned dependencies, and build integrity.

## Checklist
- Gather context from engagement goal and prior findings.
- Apply domain-specific heuristics; cite evidence for each claim.
- Flag uncertainty explicitly; do not invent IOCs or CVEs.

## Output format
Return structured JSON aligned with persona schema: concise `summary`, actionable fields, `confidence` 0–1.
