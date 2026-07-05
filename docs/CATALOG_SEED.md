# Catalog seed policy (Stream C)

Production agent definitions must come from the **dynamic catalog API/DB**, not from filesystem personas at runtime.

## Supported bootstrap

```http
POST /catalog/seed
```

- Loads the default profile pack (`cybersec-soc`) via `bootstrap.catalog_loader.load_profile_pack`.
- Seeds agents, skills, plans, MCP servers, and tools into Postgres-backed catalogs.
- Calls `reload_agent_registry()` so workers pick up DB definitions.

## Environment policy

| Variable | Prod | Dev/test |
|----------|------|----------|
| `USE_DYNAMIC_CATALOG` | `true` | optional |
| `USE_MEMORY_FALLBACK` | `false` | `true` for local FS merge |

When `USE_DYNAMIC_CATALOG=true` and `USE_MEMORY_FALLBACK=false`:

- `load_hybrid_registry()` reads **DB only**.
- `agents/personas/*.yaml` is **not** read at runtime.

## Operator workflow

1. Apply catalog schema / migrations.
2. `POST /catalog/seed` (operator role) or `./scripts/catalog_seed_bootstrap.sh`.
3. `POST /catalog/reload` if needed after manual edits.
4. Verify `GET /catalog/agents?profile_id=cybersec-soc`.

## Anti-patterns

- Relying on Helm to mount `agents/personas/*.yaml` into prod pods.
- Calling `AgentRegistry.load()` with filesystem loader when dynamic catalog is enabled in prod.
- Using `USE_MEMORY_FALLBACK=true` outside dev/test.

See also [CATALOG_RUNTIME_INVENTORY.md](CATALOG_RUNTIME_INVENTORY.md) and [ARCHITECTURE.md](ARCHITECTURE.md).
