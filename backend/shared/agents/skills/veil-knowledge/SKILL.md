---
name: veil-knowledge
description: Mandatory Veil knowledge graph and playbook workflow for CTI, MITRE, and procedures.
version: "1.0.0"
author: cys-agi
---

# Veil Knowledge

## When to load

Call `load_skill("veil-knowledge")` at the start of any task that needs threat intelligence, playbooks, MITRE mappings, or IOC enrichment from the Veil graph.

## Mandatory tool ladder

Use **native tool calling** (platform tool interface). Do not write JSON with a `tool_calls` field in your final answer — that only plans tools and does not run them.

1. **IOC / actor / CVE** — `ti_search_in_category` → optional `ti_get_node` / `ti_neighbors`
2. **Procedure** — `playbook_search` → `playbook_get` or `playbook_procedure`
3. **Convenience** — `enrich_ioc` delegates to `ti_search_in_category`; prefer typed tools when possible

Only use tools that are allowlisted for your persona in `agent.yaml`.

## Rules

- Do **not** finalize a finding that claims CTI, playbook, or MITRE context without ≥1 Veil MCP tool call unless you explicitly record `veil_unavailable` with the tool error.
- Cite Veil evidence (skill id, node id, technique id) in findings; never invent IOCs or playbooks.

## Reference

Egregore integration: `docs/integration/egregore-veil-mcp.md`
