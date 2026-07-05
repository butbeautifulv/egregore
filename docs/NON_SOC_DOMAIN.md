# Non-SOC domain onboarding

Add a product pack without SOC-specific personas or SIEM tools.

## Steps

1. Copy `domain/catalog/product_packs.py` pattern — define `ProductPack` with domain adapters.
2. Seed via catalog API (`POST /catalog/seed`) or `scripts/catalog_seed_bootstrap.sh`.
3. Set `USE_DYNAMIC_CATALOG=true` and `USE_MEMORY_FALLBACK=false` in prod.
4. Attach datasources with RBAC per [DATASOURCES_RBAC.md](./DATASOURCES_RBAC.md).
5. Run eval smoke: `uv run python scripts/evals/egregore_eval.py --suite tiny --limit 1 --dry-run`.

## Policy

- Use `policy_resolver.profile_policy_for(profile_id)` for persona overlays.
- Guardrails: `cys_core.application.guardrails.policy_gate` (fail-closed when policy missing).

## UI

- Profile compare: `/compare`
- Catalog quality: `/catalog`
