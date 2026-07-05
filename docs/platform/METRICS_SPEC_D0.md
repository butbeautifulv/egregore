# Metrics spec — D0 stubs and policy fallback

## Stub tool usage (p0-11)

```
cys_tool_stub_invocation_total{tool, persona, profile_id, reason}
```

| Label | Values |
|-------|--------|
| `tool` | tool name |
| `persona` | agent persona |
| `profile_id` | catalog profile |
| `reason` | `unconfigured`, `disabled`, `sandbox_only` |

Increment when a tool resolves to a stub handler instead of real integration.

## Policy / infrastructure fallback (p0-12)

Existing:

```
cys_infrastructure_fallback_total{component, reason}
cys_persistence_fallback_total{component}
```

| Component | Example reasons |
|-----------|-----------------|
| `kafka_queue` | `broker_unavailable`, `decode_error` |
| `kafka_bus` | `broker_unavailable`, `publish_failed` |
| `redis_bus` | `connect_failed`, `handler_failed` |
| `rate_limit` | `redis_unavailable` |

**Severity:** WARNING in logs + metric increment; never silent `except: pass` on hot paths.
