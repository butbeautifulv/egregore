# DDD / Clean Architecture Refactor — Complete

Phases R0–R8 and shim removal (R5.10) are done.

**Historical**: paths below predate the `backend/{worker,api}` package split
(`docs/MICROSERVICES_SPLIT_PLAN.md`) — `cys_core/domain/` etc. now live
under each package's own `backend/{worker,api}/src/cys_core/domain/` (no
shared package between them, see §18), and the `Verify locally` command
below applies as-is within either package.

## Layout

| Layer | Path |
|-------|------|
| Domain | `cys_core/domain/` |
| Application | `cys_core/application/` (ports, use-cases) |
| Infrastructure | `cys_core/infrastructure/` |
| Product load | `bootstrap/product_loader.py` |
| DI / settings | `bootstrap/container.py`, `bootstrap/settings.py` |
| Registry / runtime | `cys_core/registry/`, `cys_core/runtime/` |
| Delivery | `interfaces/` (api, ingress, worker, control_plane, gateways, rag, cli) |

## Definition of Done

- [x] Import-linter contracts green (`uv run lint-imports`)
- [x] Domain coverage gate 100% in CI
- [x] Application use-cases + ports split
- [x] Bootstrap DI container
- [x] Delivery moved to `interfaces/`; root shims removed
- [x] Legacy `graph/`, `coordinator/deep_assessment.py` deleted
- [x] `AgentDefinition` — product/runtime contract via `product_loader`
- [x] CLI: `uv run cys-agi`
- [ ] Application ≥90% / infrastructure ≥95% coverage fail gates (report-only in CI until green)

## Verify locally

```bash
uv run lint-imports
uv run ruff check .
./scripts/pytest_batches.sh --cov --domain-gate   # run within backend/worker or backend/api
uv run python scripts/arch_audit.py
```
