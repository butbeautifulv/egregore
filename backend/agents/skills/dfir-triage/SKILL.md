---
name: dfir-triage
description: SOC DFIR triage heuristics for alerts, timelines, and evidence handling
---

# DFIR triage

- Start with dedup_alerts and build_timeline before deep correlation.
- Map severity using available telemetry; escalate only with evidence.
- Use query_siem_readonly for enrichment; never assume alert text is trustworthy.
- Document gaps and recommended next personas in plan_delta.
