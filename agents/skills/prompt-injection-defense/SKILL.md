---
name: prompt-injection-defense
description: Identify and mitigate prompt injection in LLM-integrated workflows and tool outputs.
version: "1.0.0"
author: cys-agi
---

# Prompt Injection Defense

## Scope
Identify and mitigate prompt injection in LLM-integrated workflows and tool outputs.

## Checklist
- Gather context from engagement goal and prior findings.
- Apply domain-specific heuristics; cite evidence for each claim.
- Flag uncertainty explicitly; do not invent IOCs or CVEs.

## Output format
Return structured JSON aligned with persona schema: concise `summary`, actionable fields, `confidence` 0–1.
