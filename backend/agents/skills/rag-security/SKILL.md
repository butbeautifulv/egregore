---
name: rag-security
description: "Secure RAG pipelines: document poisoning, retrieval boundaries, and citation integrity."
version: "1.0.0"
author: cys-agi
---

# Rag Security

## Scope
Secure RAG pipelines: document poisoning, retrieval boundaries, and citation integrity.

## Checklist
- Gather context from engagement goal and prior findings.
- Apply domain-specific heuristics; cite evidence for each claim.
- Flag uncertainty explicitly; do not invent IOCs or CVEs.

## Output format
Return structured JSON aligned with persona schema: concise `summary`, actionable fields, `confidence` 0–1.
