# Catalog runtime inventory (Stream C / cat-01)

Call paths that load agent definitions at runtime.

## Dynamic catalog enabled (`USE_DYNAMIC_CATALOG=true`)

| Entry | Path | FS read in prod |
|-------|------|-----------------|
| Registry load | `cys_core/registry/agents.py` → `load_hybrid_registry()` | No when `USE_MEMORY_FALLBACK=false` |
| Reload | `hybrid_registry.reload_agent_registry()` | No when `USE_MEMORY_FALLBACK=false` |
| Catalog CLI | `scripts/catalog_cli.py` | Dev only |
| API seed | `interfaces/api/catalog.py` POST `/catalog/seed` | N/A (writes DB) |
| Registry factory | `infrastructure/catalog/registry_factory.py` | Via reload hook |

## Filesystem-only path (`USE_DYNAMIC_CATALOG=false`)

| Entry | Path | Notes |
|-------|------|-------|
| `AgentRegistry.load()` | `bootstrap/agent_definitions_loader.py` | Reads `agents/personas/*.yaml` |
| Tests | `tests/registry/test_agent_registry.py` | Uses loader fixture |

## Policy (cat-04 / cat-05 / cat-06)

- **Prod:** `USE_DYNAMIC_CATALOG=true`, `USE_MEMORY_FALLBACK=false` → DB catalog only, no FS merge.
- **Dev/test:** `USE_MEMORY_FALLBACK=true` → optional FS merge for local personas.
- **Reload:** `reload_agent_registry()` re-reads DB; FS merge only when memory fallback is enabled.

## Related runtime consumers

- `get_agent_registry()` — worker orchestrator, CLI, metrics seeding
- `get_agent_catalog()` — plan investigation, MCP catalog, profile policy
- `resource_source.list_worker_personas()` — Kafka queue persona list (legacy; queue now single-topic)
