# Python runtime hardening — async boundary inventory

Stream F wave F0 (`unified-py-01`). Classifies every `asyncio.run` / `create_task` site in egregore
before lifecycle and typing refactors.

## Allowed boundaries

| Boundary | Rule |
|----------|------|
| CLI entrypoints | `asyncio.run` is allowed in `if __name__ == "__main__"` and explicit CLI wrappers |
| Test adapters | Sync helpers allowed when tests patch async paths |
| App hot paths | Must use async APIs; sync wrappers must call `run_sync_from_sync_context` guard |
| Background work | Must be tracked by a supervisor with shutdown cancellation |

## `asyncio.run` sites (19 total)

| File | Line | Classification | Notes |
|------|------|----------------|-------|
| `interfaces/worker/daemon.py` | 70 | CLI-only | `run_worker_daemon()` wrapper |
| `interfaces/cli/main.py` | 75 | CLI-only | CLI entry |
| `interfaces/ingress/router_consumer.py` | 63 | CLI-only | consumer daemon wrapper |
| `interfaces/control_plane/bus_consumer.py` | 60 | CLI-only | bus consumer wrapper |
| `scripts/benchmarks/gaia_run.py` | 97 | CLI-only | benchmark script |
| `cys_core/infrastructure/kafka_queue.py` | 96, 99 | Infra sync port | Guarded; prefer `aenqueue`/`adequeue` in async workers |
| `cys_core/infrastructure/kafka_bus.py` | 51 | Infra sync port | `send()` for legacy sync callers |
| `cys_core/infrastructure/kafka_events.py` | 29 | Infra sync port | `publish_raw_event_sync` |
| `cys_core/infrastructure/kafka_audit.py` | 29 | Infra sync port | audit publish sync helper |
| `cys_core/infrastructure/kafka_control_events.py` | 30, 70 | Infra sync port | control/escalation sync helpers |
| `cys_core/infrastructure/kafka_paused.py` | 40 | Infra sync port | paused-job sync helper |
| `interfaces/gateways/tool/approval.py` | 74 | App-path risk | HITL approval from sync tool path |
| `cys_core/application/use_cases/delegate_research.py` | 100 | App-path risk | sync `execute` on async delegate |
| `cys_core/infrastructure/bus_transport.py` | 100 | App-path risk | Redis subscriber thread calls `asyncio.run` |

## `create_task` sites

| File | Line | Classification | Notes |
|------|------|----------------|-------|
| `interfaces/api/app.py` | 74 | App-path | Gauge refresh loop → task supervisor |
| `interfaces/api/app.py` | 145 | App-path | Async manual planner → task supervisor |
| `cys_core/infrastructure/bus_transport.py` | 102 | App-path risk | Fire-and-forget async handlers from Redis thread |

## Hot-path resource gaps (F1 targets)

| Component | Gap | Todo | Status |
|-----------|-----|------|--------|
| `KafkaJobQueue` | No `aclose()`; `cfg` NameError in `_ensure_consumer` | py-03, py-04 | done |
| `KafkaPublisher` | One-shot producers per publish call | py-05 | done |
| `KafkaBusTransport` | Long-lived producer without shutdown | py-05 | done |
| `RedisBusTransport` | Subscriber thread + unbounded `create_task` | py-09 | done |
| `RedisRateLimiter` | Async Redis client never closed | py-10 | done |
| FastAPI planner | Exception only logged | py-07, py-08 | done |
| HTTP tool adapters | Ad hoc `httpx` | py-11 | done |
| `Settings` | Weak prod/Kafka validation | py-12, py-13 | done |
| Job queue port | `dict[str, Any]` payloads | py-15 | done |
| Error hierarchy | Silent `except: pass` on hot paths | py-16 | done |
| Tests/fixtures | Timeout/cancel + async fixtures | py-19, py-20 | done |
| Layer contracts | Ports free of infrastructure imports | py-21 | done |

## Call paths to preserve (DDD)

```
interfaces/* → application/use_cases → application/ports (Protocols)
                ↓
         infrastructure/* (adapters implement ports)
```

Infrastructure must not be imported from `cys_core/domain` or `cys_core/application` except via ports/DI.
