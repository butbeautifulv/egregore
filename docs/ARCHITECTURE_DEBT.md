# Architecture debt tracker

Full audit (2026-07-05): [`BACKEND_LAYER_AUDIT.md`](BACKEND_LAYER_AUDIT.md), [`BACKEND_DRY_BACKLOG.md`](BACKEND_DRY_BACKLOG.md).

## Resolved

### Phase 7 — Observability and bootstrap ports (2026-07) — **RESTORED**

Waves A–E remediation (2026-07-05) restored green application gates and `make verify-architecture`:

- Application layer: `BusGuardConfig`, `BusDedupPort`, `MetricsPort`, `EngagementEgressPort`, `SchemaRegistryPort`, catalog mutation funnel
- Interfaces: API routers use `bootstrap.container` only (`interfaces/api → infrastructure` allowlist: `app.py` health probe only)
- Infrastructure: `ResilientRedisClient`, `resolve_persistence_store`, settings injected from container (no new bootstrap allowlist growth)
- Aggregates: `InvestigationState` / `InvestigationStateStore` deprecated; `platform_gauges` reads `EngagementStateStore`

Arch gates: `ALLOWLIST_APPLICATION_*` empty; `ALLOWLIST_INFRASTRUCTURE_USE_CASES` empty; `make verify-architecture` green.

| Port | Purpose |
|------|---------|
| `MetricsPort` | Prometheus counters/gauges for jobs, trust, memory, sanitizer |
| `CorrelationIdPort` | Bind/reset correlation ID for ingress and engagement |
| `WorkerTracingPort` | Worker span context manager |
| `TraceFlushPort` | Flush Langfuse traces after engagement dispatch |
| `ProductPackPort` | Resolve product pack for domain routing |
| `CatalogSeedLoadersPort` | Load skills/plans/MCP servers during catalog seed |
| `PolicyDefaultsPort` | Seed default profile policy |
| `ApplicationSettingsPort` | Narrow settings surface (optional; some use cases use `runtime_config` shims) |

`declared_trust_score` lives in `cys_core/domain/catalog/trust.py`.

### Phase 8 — Domain purity pragmatic (2026-07)

Structural purity in `cys_core/domain/`:

- No `cys_core.infrastructure.*` imports (static or lazy); gated by `check_domain_no_infrastructure()`
- Plan YAML I/O moved to `cys_core/application/plans/plan_loader.py`; domain keeps `parse_plan_routing_from_dict`
- Impure policy lookups moved to `cys_core/infrastructure/policy/*_adapter.py`
- `Engagement`, `WorkerJob` expose lifecycle methods; stores persist only
- `derive_run_status` in `cys_core/domain/runs/status_policy.py`
- `EngagementPlan` is the single planner output type (replaces application `InvestigationPlan`)
- API `EngagementCreateIn` is standalone with `to_domain_request()` (no domain subclass)

**Pragmatic policy:** domain models remain Pydantic `BaseModel` for serialization; rich behavior added via methods, not dataclass migration.

## Open follow-ups

| Item | Layer | Notes |
|------|-------|-------|
| `rapidfuzz` in `domain/security/sanitizer.py` | domain | Accepted third-party dep for fuzzy injection detection |
| Remove deprecated `InvestigationState` stores | domain/memory | Deprecated; episodic memory retained |

## Remediation roadmap (Waves A–E)

| Wave | Goal | Est. PRs |
|------|------|----------|
| **A** | Green application import gates (ports for guardrails + egress + registry) | 3–4 |
| **B** | Single catalog write funnel via `CatalogMutationService` | 2–3 |
| **C** | Deprecate `InvestigationState`; engagement-only aggregate | 2 |
| **D** | DRY: Redis client, store factories, control handlers, worker builder | 4–5 |
| **E** | Thin API routers; infra bootstrap cleanup; orchestrator ports | 3–4 |

**Gate extensions (Phase 4 audit):** `interfaces/api → infrastructure` check, `infrastructure → use_cases` check, `tests/architecture/test_layer_contracts.py` for shrink-only allowlists.
