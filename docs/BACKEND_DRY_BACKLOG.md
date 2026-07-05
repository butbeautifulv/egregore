# Backend DRY backlog — egregore

Prioritized refactoring backlog from layer audit (2026-07-05).  
Companion: [`BACKEND_LAYER_AUDIT.md`](BACKEND_LAYER_AUDIT.md).

Effort: **S** ≤1 day, **M** 2–3 days, **L** ≥1 week.

---

## P0 — Layer integrity + catalog funnel

| ID | Cluster | Files | Abstraction | LOC dup est. | Risk if unfixed | Effort | Wave |
|----|---------|-------|-------------|--------------|-----------------|--------|------|
| D01 | Application guardrails regressions | `bus_ingress_router.py`, `engagement_bus_guard.py`, `enqueue_worker_jobs.py`, `fail_engagement_guardrail.py` | `ApplicationSettingsPort`, `BusDedupPort`, `MetricsPort` | ~80 | Gates red; untestable application layer | M | A |
| D02 | Direct egress in application | `plan_investigation.py`, `finding_publisher.py` | `EngagementEgressPort.publish_event` | ~40 | SSE/UI coupling to infra | S | A |
| D03 | Registry in application | `process_finding_critic.py` | `SchemaRegistryPort` | ~15 | Layer violation | S | A |
| D04 | Catalog quality bypass | `update_persona_quality.py` | `CatalogMutationService.upsert_agent` | ~30 | No audit on trust updates | S | B |
| D05 | Plan quality bypass | `update_plan_quality.py` | `CatalogMutationService.upsert_plan` | ~25 | No audit on plan stats | S | B |
| D06 | API catalog inconsistency | `interfaces/api/catalog.py` | single `_mutation()` for agents + DELETE | ~50 | Operator confusion; split brain | M | B |

---

## P1 — Aggregates + infrastructure patterns

| ID | Cluster | Files | Abstraction | LOC dup est. | Risk if unfixed | Effort | Wave |
|----|---------|-------|-------------|--------------|-----------------|--------|------|
| D07 | Parallel state models | `InvestigationState`, `Engagement`, both store pairs | Deprecate investigation; engagement only | ~200 | Two sources of truth | L | C |
| D08 | Redis connect/fallback | `queue.py`, `bus_dedup_store.py`, `bus_transport.py`, `redis_egress.py`, `engagement_bus_guard.py`, `rate_limit.py` | `ResilientRedisClient` | ~150 | Bug fixes need 6× edits | M | D |
| D09 | Bootstrap outside allowlist | 8 infra/runtime files (see audit V10–V17) | settings via container injection | ~60 | Gate noise; hidden DI | M | E |
| D10 | Orchestrator observability | `interfaces/worker/orchestrator.py` | `MetricsPort`, `WorkerTracingPort` | ~40 | ARCHITECTURE_DEBT open item | S | E |
| D11 | Seed catalog bypass | `seed_catalog.py`, `cli/main.py`, `container._ensure_dev_catalog_seeded` | `CatalogMutationService` bulk API | ~80 | Unaudited catalog drift in dev | M | B |

---

## P2 — Factory and handler duplication

| ID | Cluster | Files | Abstraction | LOC dup est. | Risk if unfixed | Effort | Wave |
|----|---------|-------|-------------|--------------|-----------------|--------|------|
| D12 | Store factories | `memory/factory.py`, `engagement/store_factory.py`, `job_store/factory.py` | `PersistenceStoreFactory[T]` | ~90 | 3× postgres/memory switch bugs | M | D |
| D13 | Engagement store methods | `engagement/memory_store.py`, `postgres_store.py` | domain methods only; shared upsert helper | ~120 | Logic drift memory vs PG | M | C |
| D14 | Control-plane handlers | `coordinator_handler.py`, `critic_handler.py` | `ControlMessageHandler` base | ~50 | Copy-paste error handling | S | D |
| D15 | Start engagement egress | `start_engagement.py` | `EngagementPhasePublisher` | ~60 | Repeated status blocks | S | D |
| D16 | Route sync/async | `route_and_enqueue.py` | shared `_dispatch_routing()` | ~80 | Drift between execute/aexecute | S | D |
| D17 | Profile upsert twins | `upsert_profile_pack.py`, `upsert_profile_policy.py` | `UpsertProfileBase` | ~70 | Same merge/reload flow | S | D |
| D18 | API engagements wiring | `interfaces/api/engagements.py` | `ListTenantMemory`, `PromotePlan` use cases only | ~30 | Fat router | S | E |
| D19 | Infra narrator inversion | `control_narrator.py` | `NarrationPort` implemented by infra | ~40 | Unusual hexagon | S | D |

---

## P3 — Nice-to-have

| ID | Cluster | Files | Abstraction | LOC dup est. | Risk if unfixed | Effort | Wave |
|----|---------|-------|-------------|--------------|-----------------|--------|------|
| D20 | Thin upsert use cases | `upsert_catalog_resource.py` | generic `upsert_catalog_entry(type, dto)` | ~40 | Low — already small | S | — |
| D21 | Worker pipeline wiring | `container.get_run_worker_job`, `tests/.../factory.py` | `build_worker_pipeline(deps)` | ~100 | Test/production drift | M | D |
| D22 | Metrics configure modules | `budget_metrics.py`, `sgr_iron_metrics.py`, `persona_quality_hooks.py` | single `MetricsRegistry` wire | ~45 | Scattered init | S | D |
| D23 | Noop triple guard | `run_worker_job`, `finding_publisher` | single `NoopFindingGuard` at pipeline edge | ~30 | Noise only | S | — |
| D24 | Job finalizer outcomes | `job_finalizer.py` | `JobOutcomePublisher` | ~50 | Repeated egress shapes | S | D |

---

## Suggested execution order

1. **D01–D03** (Wave A) — restore green application gates  
2. **D04–D06, D11** (Wave B) — catalog funnel  
3. **D07, D13** (Wave C) — engagement aggregate consolidation  
4. **D08, D12, D14–D17, D19, D21–D24** (Wave D) — DRY extractions  
5. **D09, D10, D18** (Wave E) — interfaces + infra bootstrap  

---

## What's already DRY (do not refactor)

- Worker pipeline: `RunWorkerJob` + `workers/*` decomposition (Phase 6)
- Secondary catalogs: `JsonPayloadCatalog` / `PostgresJsonCatalog`
- `noop_signals` shared by bus, publisher, critic
- `CatalogMutationService` exists — adoption incomplete, not absence of abstraction
- `MetaPlanner` → `PlanInvestigation` delegation
