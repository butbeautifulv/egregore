---
name: siem-investigation
description: Mandatory MaxPatrol SIEM investigation workflow for SOC triage.
version: "1.0.0"
author: cys-agi
---

# SIEM Investigation

## When to load

Call `load_skill("siem-investigation")` at the start of any SOC engagement that involves SIEM alerts or incidents.

## Mandatory tool ladder

1. **Queue** — If no incident ID is known: `list_incidents` (filter mentally to New/InProgress).
2. **Triage** — `investigate_incident(incident_id)` is the primary entry point for a known incident.
3. **Drill-down** — Use `search_events` (PDQL `where`) or `get_event_by_uuid` for event-level detail.
4. **Enrichment** — `lookup_assets_by_ip` for targets; `export_table_list` for IOC/table lookups when needed.
5. **Audit** — `search_user_actions` when incident ownership or status changes matter.

## Rules

- Do **not** finalize a finding without at least one SIEM MCP tool call (`investigate_incident`, `search_events`, `list_incidents`, …) unless you explicitly record `siem_unavailable` with the error from the tool.
- Prefer typed tools over generic HTTP; do **not** use raw `siem_request` when a typed tool exists.
- Cite SIEM evidence via `evidence[].obs_id` refs from `evidence_manifest`; never invent events or process details.

## KATA / TAA sparse alerts

When `evidence_manifest.telemetry_level` is `sparse` or `metadata_only` (e.g. `malicious_pipe_created`, `kata_taa_high_alert` without cmdline/account fields):

- Summarize only host, correlation rule, and incident key from manifest observations.
- Populate `data_gaps` from manifest (include `remediation` for KATA console when `required_external_sources` contains `kata_taa_console`).
- Set `confidence <= evidence_manifest.max_confidence` (typically 0.5).
- Do **not** infer Mimikatz, credential dumping, or specific process/pipe names without matching observations.

## Veil enrichment after SIEM

Use `playbook_search` with keywords from incident name/type (e.g. port scan → `playbook_search(query="port scan")`). MITRE technique mapping (`playbook_for_technique`) is handled by the **intel** persona, not SOC.

## Reference

MaxPatrol SIEM MCP workflow: `projects/maxpatrol-siem-mcp/README.md`
