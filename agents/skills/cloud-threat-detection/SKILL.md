---
name: cloud-threat-detection
description: Cloud control-plane and workload threat detection (IAM, storage, K8s).
version: "1.0.0"
author: cys-agi
---

# Cloud Threat Detection

## Scope
Cloud control-plane and workload threat detection (IAM, storage, K8s).

## Checklist
- Gather context from engagement goal and prior findings.
- Apply domain-specific heuristics; cite evidence for each claim.
- Flag uncertainty explicitly; do not invent IOCs or CVEs.

## Output format
Return structured JSON aligned with persona schema: concise `summary`, actionable fields, `confidence` 0–1.
