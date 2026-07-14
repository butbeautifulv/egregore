# Egregore 2ENV inventory

**status:** done  
**epic:** hardcode → `bootstrap/settings.py` + wiring (P1 audit, P2 fix, P3 deploy sync)  
**parity guard:** `tests/application/test_runtime_config_defaults_sync.py`

## Summary

| Metric | Count |
|--------|------:|
| `# TODO: 2ENV` markers placed (P1) | ~115 |
| Runtime `.py` files touched | ~32 |
| New / wired `Settings` fields (P2) | ~55 |
| Markers remaining in scope | **0** |

Skipped (out of scope): `tests/**`, `refs/**`, `settings.py` Field defaults, HTTP status codes, persona names, k8s label keys, `scripts/` (optional P1.9b).

## Wiring patterns

| Pattern | When |
|---------|------|
| `configure_from_settings()` | `runtime_config` mirrors of `Settings` |
| `container` constructor | use-case deps, job cost, persona budgets |
| `get_settings()` at call site | interfaces, adapters, domain helpers |
| `env_overrides_from_settings()` | catalog profile policy env shim |
| `persona_budget_loader.load_persona_budgets()` | `PERSONA_BUDGETS_OVERRIDES_JSON` |

## P2 subphases (completed)

| Subphase | Files | ENV examples |
|----------|-------|--------------|
| P2.1 | `runtime_config.py`, `container.py` | existing `Settings` mirrors |
| P2.2 | `interfaces/api/app.py` | `API_GAUGE_REFRESH_INTERVAL_S`, `API_RECONCILE_*`, `API_SSE_*` |
| P2.3 | `http_client.py`, `mcp_tools.py`, `veil_mcp_client.py` | `HTTP_CONNECT_TIMEOUT_S`, `HTTP_READ_TIMEOUT_S` |
| P2.4 | `run_worker_job.py`, `reconcile_stuck_engagements.py` | `WORKER_*_ATTEMPTS`, `RECONCILE_SYNTHESIS_STALE_MULTIPLIER` |
| P2.5 | bus ingress / transport / kafka / `follow_up_aggregator` | `BUS_*`, `KAFKA_CONSUME_TIMEOUT_S` |
| P2.6 | `k8s_sandbox.py`, `docker_sandbox.py` | `K8S_SANDBOX_*`, `DOCKER_*` |
| P2.7 | `tool_execution_tracker`, `egress_streaming_callback`, `timeout_salvage` | `TOOL_OUTPUT_*`, `EGRESS_*`, `TIMEOUT_SALVAGE_SUMMARY_MAX` |
| P2.8 | `enqueue_follow_up.py` | `FOLLOW_UP_CONVERSATION_QUERY_LIMIT`, `FOLLOW_UP_HISTORY_LIMIT` |
| P2.9 | `job_budget.py` | `JOB_COST_PER_1K_TOKENS_USD` |
| P2.10 | `persona_budget_loader.py`, `defaults.py` | `PERSONA_BUDGETS_OVERRIDES_JSON` |
| P2.11 | `manifest_builder.py`, `noop.py`, `catalog/models.py`, `policy_resolver.py` | `EVIDENCE_*`, `NOOP_*`, profile env shim |
| P2.12 | `multimodal.py`, `web_search.py`, `search_stack.py`, `siem.py` | `WAYBACK_API_TIMEOUT_S`, search/SIEM API timeouts |
| P2.13 | `cli/main.py`, `worker/daemon.py`, `orchestrator.py` | `EGREGORE_METRICS_PORT`, `WORKER_DEQUEUE_TIMEOUT_S` |
| P2.14 | this doc, `egregore-local.env.example`, parity test | — |
| P3 | `deploy/k8s/cxado-offline/values-egregore-offline.yaml` | helm `env:` camelCase keys |

## Operator-facing ENV (P2 additions)

| ENV | Settings field | Default | Category |
|-----|----------------|---------|----------|
| `API_GAUGE_REFRESH_INTERVAL_S` | `api_gauge_refresh_interval_s` | 30 | timeout |
| `API_RECONCILE_INTERVAL_S` | `api_reconcile_interval_s` | 300 | timeout |
| `API_RECONCILE_LEADER_TTL_S` | `api_reconcile_leader_ttl_s` | 280 | timeout |
| `API_SSE_QUEUE_TIMEOUT_S` | `api_sse_queue_timeout_s` | 15 | timeout |
| `API_SSE_RETRY_SLEEP_S` | `api_sse_retry_sleep_s` | 2 | timeout |
| `HTTP_CONNECT_TIMEOUT_S` | `http_connect_timeout_s` | 10 | timeout |
| `HTTP_READ_TIMEOUT_S` | `http_read_timeout_s` | 120 | timeout |
| `WORKER_TRIAGE_MAX_ATTEMPTS` | `worker_triage_max_attempts` | 2 | limit |
| `WORKER_MAX_ATTEMPTS` | `worker_max_attempts` | 3 | limit |
| `WORKER_MAX_DEPENDENCY_DEFERRALS` | `worker_max_dependency_deferrals` | 10 | limit |
| `WORKER_SOFT_TIMEOUT_FRACTION` | `worker_soft_timeout_fraction` | 0.9 | limit |
| `WORKER_DEQUEUE_TIMEOUT_S` | `worker_dequeue_timeout_s` | 2.0 | timeout |
| `RECONCILE_SYNTHESIS_STALE_MULTIPLIER` | `reconcile_synthesis_stale_multiplier` | 2.0 | limit |
| `RECONCILE_SCAN_LIMIT` | `reconcile_scan_limit` | 50 | limit |
| `BUS_SEEN_TTL_SECONDS` | `bus_seen_ttl_seconds` | 300 | timeout |
| `KAFKA_CONSUME_TIMEOUT_S` | `kafka_consume_timeout_s` | 1.0 | timeout |
| `K8S_SANDBOX_READY_POLL_INTERVAL_S` | `k8s_sandbox_ready_poll_interval_s` | 0.5 | timeout |
| `DOCKER_PROBE_TIMEOUT_S` | `docker_probe_timeout_s` | 5.0 | timeout |
| `DOCKER_KILL_TIMEOUT_S` | `docker_kill_timeout_s` | 10.0 | timeout |
| `TOOL_OUTPUT_PREVIEW_MAX` | `tool_output_preview_max` | 16384 | limit |
| `TOOL_STORED_OUTPUTS_MAX` | `tool_stored_outputs_max` | 5 | limit |
| `EGRESS_BATCH_SECONDS` | `egress_batch_seconds` | 0.05 | timeout |
| `TIMEOUT_SALVAGE_SUMMARY_MAX` | `timeout_salvage_summary_max` | 2000 | limit |
| `FOLLOW_UP_CONVERSATION_QUERY_LIMIT` | `follow_up_conversation_query_limit` | 200 | limit |
| `FOLLOW_UP_HISTORY_LIMIT` | `follow_up_history_limit` | 100 | limit |
| `FOLLOW_UP_MERGE_QUERY_LIMIT` | `follow_up_merge_query_limit` | 30 | limit |
| `FOLLOW_UP_MERGE_SUMMARY_MAX` | `follow_up_merge_summary_max` | 400 | limit |
| `JOB_COST_PER_1K_TOKENS_USD` | `job_cost_per_1k_tokens_usd` | 0.003 | budget |
| `PERSONA_BUDGETS_OVERRIDES_JSON` | `persona_budgets_overrides_json` | "" | budget |
| `DEFAULT_PERSONA_MAX_TOOL_CALLS` | `default_persona_max_tool_calls` | 50 | budget |
| `CRITIC_TRUST_THRESHOLD` | `critic_trust_threshold` | 0.5 | limit |
| `CRITIC_DEFAULT_CONFIDENCE` | `critic_default_confidence` | 0.5 | limit |
| `PLANNER_DEFAULT_POST_PROCESSORS` | `planner_default_post_processors` | comma list | limit |
| `EVIDENCE_EVENT_TEXT_MAX` | `evidence_event_text_max` | 500 | limit |
| `EVIDENCE_MAX_CONFIDENCE_METADATA` | `evidence_max_confidence_metadata` | 0.3 | limit |
| `EVIDENCE_MAX_CONFIDENCE_SPARSE` | `evidence_max_confidence_sparse` | 0.5 | limit |
| `EVIDENCE_MAX_CONFIDENCE_RICH` | `evidence_max_confidence_rich` | 1.0 | limit |
| `NOOP_LOW_CONFIDENCE_THRESHOLD` | `noop_low_confidence_threshold` | 0.25 | limit |
| `NOOP_PENDING_TRUST_THRESHOLD` | `noop_pending_trust_threshold` | 0.3 | limit |
| `WAYBACK_API_TIMEOUT_S` | `wayback_api_timeout_s` | 20 | timeout |
| `EGREGORE_METRICS_PORT` | `egregore_metrics_port` | 9091 | limit |

Profile policy catalog defaults (`max_spawn_depth`, `delegate_budget_fraction`, `cost_per_1k_tokens_usd`) remain YAML defaults; runtime overrides use existing `MAX_SPAWN_DEPTH`, `DELEGATE_BUDGET_FRACTION`, `JOB_COST_PER_1K_TOKENS_USD` via `env_overrides_from_settings()`.

## Verify

```bash
cd projects/egregore
rg '# TODO: 2ENV' --glob '*.py' --glob '!tests/**' --glob '!refs/**'   # expect 0
./scripts/pytest_batches.sh tests/application/test_runtime_config_defaults_sync.py
USE_MEMORY_FALLBACK=true STAGE=test uv run egregore info
```
