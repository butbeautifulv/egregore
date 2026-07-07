# Tool matrix (generated)

Auto-generated from `ToolProviderPort` metadata. Regenerate: `scripts/generate_tool_matrix.py`.

## Offline-disabled builtin stubs

These tools return canned JSON and are removed from persona `tools:` lists in offline deployments:

`dedup_alerts`, `build_timeline`, `correlate_findings`, `parse_netflow`, `correlate_dns`, `check_control`, `map_framework`, `audit_evidence`, `query_siem_readonly` (use SIEM MCP instead), `web_search`, `search_archived_webpage`.

## Profile: `cybersec-soc`

| Tool | Module | Status | Datasource | Description |
|------|--------|--------|------------|-------------|
| `analyze_workflow` | builtin | real | — | Analyze CI/CD workflow for risky patterns (pull_request_target, secrets in env). |
| `audit_evidence` | builtin | real | — | Audit evidence retention and auditability. |
| `build_timeline` | builtin | real | — | Build incident timeline from correlated events. |
| `check_control` | builtin | real | — | Check compliance control against provided evidence. |
| `correlate_dns` | builtin | real | — | Correlate DNS events for beaconing patterns. |
| `correlate_findings` | builtin | real | — | Correlate findings across telemetry sources. |
| `dedup_alerts` | builtin | real | — | Deduplicate and cluster SIEM alerts. |
| `enrich_ioc` | builtin | real | — | Enrich IP/domain IOC via Veil threat-intel when available. |
| `map_framework` | builtin | real | — | Map observation to compliance framework controls. |
| `parse_netflow` | builtin | real | — | Parse NetFlow summary text into structured indicators. |
| `parse_sast_report` | builtin | real | — | Parse SAST report JSON and extract high-signal findings. |
| `read_repo_metadata` | builtin | real | — | Read repository metadata (languages, branches, recent commits). Stub for authorized scope. |
| `search_personas` | discovery | real | — | Search registered agent personas by keyword. |
| `search_skills` | discovery | real | — | Search product skills by keyword. |
| `search_tools` | discovery | real | — | Search available tools filtered by interaction mode policy. |
| `ask_user` | orchestration | real | — | Pause run and surface a clarifying question to the operator. |
| `create_report_outline` | orchestration | real | — | Skeleton-of-Thoughts: create report outline before section fill. |
| `delegate_research` | orchestration | real | — | Delegate a read-only research subtask to the research persona in-process. |
| `extract_structured_output` | orchestration | real | — | Extract structured deliverable with confidence and weaknesses. |
| `plan_tool_calls` | orchestration | real | — | ReWOO-style upfront tool plan (search → read → extract) without reactive loops. |
| `reasoning_check` | orchestration | real | — | Review full action trace before final synthesis (DeepAgent reasoning step). |
| `reasoning_step` | orchestration | real | — | Mandatory schema-guided reasoning step before action tools (SGR). |
| `spawn_worker` | orchestration | real | — | Enqueue a specialist worker spawned from the active conductor session. |
| `update_todos` | orchestration | real | — | Replace work todos for the active run context. |
| `rag_query` | rag | real | rag-index | Retrieve ACL-filtered knowledge base chunks via MCP Tool Gateway. |
| `browser_use` | sandbox | stub | — | Headless browser actions. Disabled unless BROWSER_ENABLED=true. |
| `execute_command` | sandbox | real | — | Execute shell command. RESTRICTED — should be denied for most agents. |
| `python_sandbox` | sandbox | stub | — | Execute Python code in a restricted local subprocess. Requires HITL approval. |
| `run_active_scan` | sandbox | stub | — | Run active security scan on authorized target. Requires HITL approval. |
| `query_siem_readonly` | siem | real | siem-readonly | Execute read-only SIEM search. Worker runs route via MCP Tool Gateway. |
| `export_table_list` | siem-mcp | real | siem-mcp | Export tabular IOC/list data from SIEM table lists for lookup during triage. |
| `get_event_by_uuid` | siem-mcp | real | siem-mcp | Fetch one SIEM event by UUID for drill-down after investigate_incident or search_events. |
| `investigate_incident` | siem-mcp | real | siem-mcp | Use FIRST when triaging a SIEM incident by ID. Returns incident summary, correlated events, and optional asset/IOC context. Do NOT use siem_request if this tool applies. |
| `list_aggregated_events` | siem-mcp | real | siem-mcp | List aggregated SIEM events for timeline visualization around an incident window. |
| `list_incidents` | siem-mcp | real | siem-mcp | List SIEM incidents (New/InProgress queue). Use before investigate_incident when no incident ID is known. |
| `lookup_assets_by_ip` | siem-mcp | real | siem-mcp | Enrich investigation targets: resolve assets by IP from SIEM asset inventory. |
| `search_api_docs` | siem-mcp | real | siem-mcp | Escape hatch: search local MaxPatrol SIEM API docs when typed tools are insufficient. |
| `search_events` | siem-mcp | real | siem-mcp | Search SIEM events by PDQL where clause for correlation and timeline enrichment. Use after investigate_incident when you need additional predicates. |
| `search_user_actions` | siem-mcp | real | siem-mcp | Audit who changed an incident or SIEM object (user action log). |
| `playbook_for_technique` | veil-mcp | real | veil-mcp | Use when MITRE ATT&CK technique ID is known — list playbooks linked to it. |
| `playbook_framework` | veil-mcp | real | veil-mcp | Read Veil MITRE Navigator layer, coverage summary, or mapping docs. |
| `playbook_get` | veil-mcp | real | veil-mcp | Fetch full playbook markdown for a skill id from playbook_search. |
| `playbook_ontology_subdomains` | veil-mcp | real | veil-mcp | Veil subdomain registry with category mapping and priority tier. |
| `playbook_procedure` | veil-mcp | real | veil-mcp | Structured procedure steps for a playbook skill id. |
| `playbook_search` | veil-mcp | real | veil-mcp | Use FIRST when you need a cybersecurity procedure playbook by keywords and optional subdomain. |
| `playbook_subdomains` | veil-mcp | real | veil-mcp | List Anthropic skill subdomain counts from Veil playbook index. |
| `ti_get_node` | veil-mcp | real | veil-mcp | Fetch one Veil graph node by element id after ti_search_in_category. |
| `ti_health` | veil-mcp | real | veil-mcp | Veil graph API and Neo4j connectivity health check. |
| `ti_list_categories` | veil-mcp | real | veil-mcp | List Veil graph product categories (vuln, ti, mitre, playbook, …). |
| `ti_list_kinds_in_category` | veil-mcp | real | veil-mcp | List Neo4j node labels within a Veil category with counts. |
| `ti_neighbors` | veil-mcp | real | veil-mcp | Fetch k-hop subgraph around a Veil graph node for relationship context. |
| `ti_nodes_by_category` | veil-mcp | real | veil-mcp | List graph nodes for a category + kind label. |
| `ti_search_in_category` | veil-mcp | real | veil-mcp | Use FIRST for IOC/CVE/actor lookup in Veil knowledge graph within a category (optional kind). |
| `read_document` | web | real | — | Read a local document attachment (txt, md, json, csv, pdf stub). |
| `search_archived_webpage` | web | real | — | Retrieve historical webpage content via Wayback Machine. |
| `transcribe_audio` | web | real | — | Transcribe audio attachment (stub — wire STT provider in production). |
| `vision_analyze` | web | real | — | Analyze image attachments (charts, screenshots, diagrams). |
| `web_search` | web | real | — | Search the public web for OSINT and factual references (read-only). |

## Profile: `general-assistant`

| Tool | Module | Status | Datasource | Description |
|------|--------|--------|------------|-------------|
| `analyze_workflow` | builtin | real | — | Analyze CI/CD workflow for risky patterns (pull_request_target, secrets in env). |
| `audit_evidence` | builtin | real | — | Audit evidence retention and auditability. |
| `build_timeline` | builtin | real | — | Build incident timeline from correlated events. |
| `check_control` | builtin | real | — | Check compliance control against provided evidence. |
| `correlate_dns` | builtin | real | — | Correlate DNS events for beaconing patterns. |
| `correlate_findings` | builtin | real | — | Correlate findings across telemetry sources. |
| `dedup_alerts` | builtin | real | — | Deduplicate and cluster SIEM alerts. |
| `enrich_ioc` | builtin | real | — | Enrich IP/domain IOC via Veil threat-intel when available. |
| `map_framework` | builtin | real | — | Map observation to compliance framework controls. |
| `parse_netflow` | builtin | real | — | Parse NetFlow summary text into structured indicators. |
| `parse_sast_report` | builtin | real | — | Parse SAST report JSON and extract high-signal findings. |
| `read_repo_metadata` | builtin | real | — | Read repository metadata (languages, branches, recent commits). Stub for authorized scope. |
| `search_personas` | discovery | real | — | Search registered agent personas by keyword. |
| `search_skills` | discovery | real | — | Search product skills by keyword. |
| `search_tools` | discovery | real | — | Search available tools filtered by interaction mode policy. |
| `ask_user` | orchestration | real | — | Pause run and surface a clarifying question to the operator. |
| `create_report_outline` | orchestration | real | — | Skeleton-of-Thoughts: create report outline before section fill. |
| `delegate_research` | orchestration | real | — | Delegate a read-only research subtask to the research persona in-process. |
| `extract_structured_output` | orchestration | real | — | Extract structured deliverable with confidence and weaknesses. |
| `plan_tool_calls` | orchestration | real | — | ReWOO-style upfront tool plan (search → read → extract) without reactive loops. |
| `reasoning_check` | orchestration | real | — | Review full action trace before final synthesis (DeepAgent reasoning step). |
| `reasoning_step` | orchestration | real | — | Mandatory schema-guided reasoning step before action tools (SGR). |
| `spawn_worker` | orchestration | real | — | Enqueue a specialist worker spawned from the active conductor session. |
| `update_todos` | orchestration | real | — | Replace work todos for the active run context. |
| `rag_query` | rag | real | rag-index | Retrieve ACL-filtered knowledge base chunks via MCP Tool Gateway. |
| `browser_use` | sandbox | stub | — | Headless browser actions. Disabled unless BROWSER_ENABLED=true. |
| `execute_command` | sandbox | real | — | Execute shell command. RESTRICTED — should be denied for most agents. |
| `python_sandbox` | sandbox | stub | — | Execute Python code in a restricted local subprocess. Requires HITL approval. |
| `run_active_scan` | sandbox | stub | — | Run active security scan on authorized target. Requires HITL approval. |
| `query_siem_readonly` | siem | real | siem-readonly | Execute read-only SIEM search. Worker runs route via MCP Tool Gateway. |
| `export_table_list` | siem-mcp | real | siem-mcp | Export tabular IOC/list data from SIEM table lists for lookup during triage. |
| `get_event_by_uuid` | siem-mcp | real | siem-mcp | Fetch one SIEM event by UUID for drill-down after investigate_incident or search_events. |
| `investigate_incident` | siem-mcp | real | siem-mcp | Use FIRST when triaging a SIEM incident by ID. Returns incident summary, correlated events, and optional asset/IOC context. Do NOT use siem_request if this tool applies. |
| `list_aggregated_events` | siem-mcp | real | siem-mcp | List aggregated SIEM events for timeline visualization around an incident window. |
| `list_incidents` | siem-mcp | real | siem-mcp | List SIEM incidents (New/InProgress queue). Use before investigate_incident when no incident ID is known. |
| `lookup_assets_by_ip` | siem-mcp | real | siem-mcp | Enrich investigation targets: resolve assets by IP from SIEM asset inventory. |
| `search_api_docs` | siem-mcp | real | siem-mcp | Escape hatch: search local MaxPatrol SIEM API docs when typed tools are insufficient. |
| `search_events` | siem-mcp | real | siem-mcp | Search SIEM events by PDQL where clause for correlation and timeline enrichment. Use after investigate_incident when you need additional predicates. |
| `search_user_actions` | siem-mcp | real | siem-mcp | Audit who changed an incident or SIEM object (user action log). |
| `playbook_for_technique` | veil-mcp | real | veil-mcp | Use when MITRE ATT&CK technique ID is known — list playbooks linked to it. |
| `playbook_framework` | veil-mcp | real | veil-mcp | Read Veil MITRE Navigator layer, coverage summary, or mapping docs. |
| `playbook_get` | veil-mcp | real | veil-mcp | Fetch full playbook markdown for a skill id from playbook_search. |
| `playbook_ontology_subdomains` | veil-mcp | real | veil-mcp | Veil subdomain registry with category mapping and priority tier. |
| `playbook_procedure` | veil-mcp | real | veil-mcp | Structured procedure steps for a playbook skill id. |
| `playbook_search` | veil-mcp | real | veil-mcp | Use FIRST when you need a cybersecurity procedure playbook by keywords and optional subdomain. |
| `playbook_subdomains` | veil-mcp | real | veil-mcp | List Anthropic skill subdomain counts from Veil playbook index. |
| `ti_get_node` | veil-mcp | real | veil-mcp | Fetch one Veil graph node by element id after ti_search_in_category. |
| `ti_health` | veil-mcp | real | veil-mcp | Veil graph API and Neo4j connectivity health check. |
| `ti_list_categories` | veil-mcp | real | veil-mcp | List Veil graph product categories (vuln, ti, mitre, playbook, …). |
| `ti_list_kinds_in_category` | veil-mcp | real | veil-mcp | List Neo4j node labels within a Veil category with counts. |
| `ti_neighbors` | veil-mcp | real | veil-mcp | Fetch k-hop subgraph around a Veil graph node for relationship context. |
| `ti_nodes_by_category` | veil-mcp | real | veil-mcp | List graph nodes for a category + kind label. |
| `ti_search_in_category` | veil-mcp | real | veil-mcp | Use FIRST for IOC/CVE/actor lookup in Veil knowledge graph within a category (optional kind). |
| `read_document` | web | real | — | Read a local document attachment (txt, md, json, csv, pdf stub). |
| `search_archived_webpage` | web | real | — | Retrieve historical webpage content via Wayback Machine. |
| `transcribe_audio` | web | real | — | Transcribe audio attachment (stub — wire STT provider in production). |
| `vision_analyze` | web | real | — | Analyze image attachments (charts, screenshots, diagrams). |
| `web_search` | web | real | — | Search the public web for OSINT and factual references (read-only). |

## Profile: `gaia-benchmark`

| Tool | Module | Status | Datasource | Description |
|------|--------|--------|------------|-------------|
| `analyze_workflow` | builtin | real | — | Analyze CI/CD workflow for risky patterns (pull_request_target, secrets in env). |
| `audit_evidence` | builtin | real | — | Audit evidence retention and auditability. |
| `build_timeline` | builtin | real | — | Build incident timeline from correlated events. |
| `check_control` | builtin | real | — | Check compliance control against provided evidence. |
| `correlate_dns` | builtin | real | — | Correlate DNS events for beaconing patterns. |
| `correlate_findings` | builtin | real | — | Correlate findings across telemetry sources. |
| `dedup_alerts` | builtin | real | — | Deduplicate and cluster SIEM alerts. |
| `enrich_ioc` | builtin | real | — | Enrich IP/domain IOC via Veil threat-intel when available. |
| `map_framework` | builtin | real | — | Map observation to compliance framework controls. |
| `parse_netflow` | builtin | real | — | Parse NetFlow summary text into structured indicators. |
| `parse_sast_report` | builtin | real | — | Parse SAST report JSON and extract high-signal findings. |
| `read_repo_metadata` | builtin | real | — | Read repository metadata (languages, branches, recent commits). Stub for authorized scope. |
| `search_personas` | discovery | real | — | Search registered agent personas by keyword. |
| `search_skills` | discovery | real | — | Search product skills by keyword. |
| `search_tools` | discovery | real | — | Search available tools filtered by interaction mode policy. |
| `ask_user` | orchestration | real | — | Pause run and surface a clarifying question to the operator. |
| `create_report_outline` | orchestration | real | — | Skeleton-of-Thoughts: create report outline before section fill. |
| `delegate_research` | orchestration | real | — | Delegate a read-only research subtask to the research persona in-process. |
| `extract_structured_output` | orchestration | real | — | Extract structured deliverable with confidence and weaknesses. |
| `plan_tool_calls` | orchestration | real | — | ReWOO-style upfront tool plan (search → read → extract) without reactive loops. |
| `reasoning_check` | orchestration | real | — | Review full action trace before final synthesis (DeepAgent reasoning step). |
| `reasoning_step` | orchestration | real | — | Mandatory schema-guided reasoning step before action tools (SGR). |
| `spawn_worker` | orchestration | real | — | Enqueue a specialist worker spawned from the active conductor session. |
| `update_todos` | orchestration | real | — | Replace work todos for the active run context. |
| `rag_query` | rag | real | rag-index | Retrieve ACL-filtered knowledge base chunks via MCP Tool Gateway. |
| `browser_use` | sandbox | stub | — | Headless browser actions. Disabled unless BROWSER_ENABLED=true. |
| `execute_command` | sandbox | real | — | Execute shell command. RESTRICTED — should be denied for most agents. |
| `python_sandbox` | sandbox | stub | — | Execute Python code in a restricted local subprocess. Requires HITL approval. |
| `run_active_scan` | sandbox | stub | — | Run active security scan on authorized target. Requires HITL approval. |
| `query_siem_readonly` | siem | real | siem-readonly | Execute read-only SIEM search. Worker runs route via MCP Tool Gateway. |
| `export_table_list` | siem-mcp | real | siem-mcp | Export tabular IOC/list data from SIEM table lists for lookup during triage. |
| `get_event_by_uuid` | siem-mcp | real | siem-mcp | Fetch one SIEM event by UUID for drill-down after investigate_incident or search_events. |
| `investigate_incident` | siem-mcp | real | siem-mcp | Use FIRST when triaging a SIEM incident by ID. Returns incident summary, correlated events, and optional asset/IOC context. Do NOT use siem_request if this tool applies. |
| `list_aggregated_events` | siem-mcp | real | siem-mcp | List aggregated SIEM events for timeline visualization around an incident window. |
| `list_incidents` | siem-mcp | real | siem-mcp | List SIEM incidents (New/InProgress queue). Use before investigate_incident when no incident ID is known. |
| `lookup_assets_by_ip` | siem-mcp | real | siem-mcp | Enrich investigation targets: resolve assets by IP from SIEM asset inventory. |
| `search_api_docs` | siem-mcp | real | siem-mcp | Escape hatch: search local MaxPatrol SIEM API docs when typed tools are insufficient. |
| `search_events` | siem-mcp | real | siem-mcp | Search SIEM events by PDQL where clause for correlation and timeline enrichment. Use after investigate_incident when you need additional predicates. |
| `search_user_actions` | siem-mcp | real | siem-mcp | Audit who changed an incident or SIEM object (user action log). |
| `playbook_for_technique` | veil-mcp | real | veil-mcp | Use when MITRE ATT&CK technique ID is known — list playbooks linked to it. |
| `playbook_framework` | veil-mcp | real | veil-mcp | Read Veil MITRE Navigator layer, coverage summary, or mapping docs. |
| `playbook_get` | veil-mcp | real | veil-mcp | Fetch full playbook markdown for a skill id from playbook_search. |
| `playbook_ontology_subdomains` | veil-mcp | real | veil-mcp | Veil subdomain registry with category mapping and priority tier. |
| `playbook_procedure` | veil-mcp | real | veil-mcp | Structured procedure steps for a playbook skill id. |
| `playbook_search` | veil-mcp | real | veil-mcp | Use FIRST when you need a cybersecurity procedure playbook by keywords and optional subdomain. |
| `playbook_subdomains` | veil-mcp | real | veil-mcp | List Anthropic skill subdomain counts from Veil playbook index. |
| `ti_get_node` | veil-mcp | real | veil-mcp | Fetch one Veil graph node by element id after ti_search_in_category. |
| `ti_health` | veil-mcp | real | veil-mcp | Veil graph API and Neo4j connectivity health check. |
| `ti_list_categories` | veil-mcp | real | veil-mcp | List Veil graph product categories (vuln, ti, mitre, playbook, …). |
| `ti_list_kinds_in_category` | veil-mcp | real | veil-mcp | List Neo4j node labels within a Veil category with counts. |
| `ti_neighbors` | veil-mcp | real | veil-mcp | Fetch k-hop subgraph around a Veil graph node for relationship context. |
| `ti_nodes_by_category` | veil-mcp | real | veil-mcp | List graph nodes for a category + kind label. |
| `ti_search_in_category` | veil-mcp | real | veil-mcp | Use FIRST for IOC/CVE/actor lookup in Veil knowledge graph within a category (optional kind). |
| `read_document` | web | real | — | Read a local document attachment (txt, md, json, csv, pdf stub). |
| `search_archived_webpage` | web | real | — | Retrieve historical webpage content via Wayback Machine. |
| `transcribe_audio` | web | real | — | Transcribe audio attachment (stub — wire STT provider in production). |
| `vision_analyze` | web | real | — | Analyze image attachments (charts, screenshots, diagrams). |
| `web_search` | web | real | — | Search the public web for OSINT and factual references (read-only). |
