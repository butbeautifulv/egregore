---
name: kill-chain-purple
description: Purple-team kill-chain mapping from detection to validation exercises.
version: "1.0.0"
author: cys-agi
---

# Kill Chain Purple

## Scope
Purple-team kill-chain mapping from detection to validation exercises.

## Checklist
- Gather context from engagement goal and prior findings.
- Apply domain-specific heuristics; cite evidence for each claim.
- Flag uncertainty explicitly; do not invent IOCs or CVEs.

## Output format
Return structured JSON aligned with persona schema: concise `summary`, actionable fields, `confidence` 0–1.
