# Kafka queue migration — per-persona topics → `worker.jobs` (Stream B que-06)

Cutover from `worker.jobs.{persona}` to a single topic `worker.jobs` with persona filtering in `KafkaJobQueue`.

## Preconditions

- Image tag includes Stream B code (`WORKER_JOBS_TOPIC`, consumer group `egregore-workers`).
- `max_poll_interval_ms` ≥ `worker_job_timeout + 120s` (see `KafkaJobQueue._max_poll_interval_ms`).
- Operators have API catalog seeded (`POST /catalog/seed` or `./scripts/catalog_seed_bootstrap.sh`).

## Cutover steps

1. **Freeze producers** — scale API/workers to 0 or enable maintenance mode.
2. **Drain legacy topics** — wait until per-persona topics (`worker.jobs.consultant`, etc.) have `LAG=0`.
3. **Create unified topic** — `worker.jobs` with 8 partitions (`deploy/k8s/cxado-offline/15-redpanda-topics-job.yaml`, que-05).
4. **Deploy new image** — workers use single consumer group `egregore-workers`; persona filter requeues non-matching jobs.
5. **Smoke** — `POST /events` manual.investigation ×2 parallel; verify jobs complete and `cys_infrastructure_fallback_total` stable.
6. **Retire legacy topics** — after 24h without traffic, delete `worker.jobs.*` per-persona topics.

## Rollback

- Revert to previous image with per-persona topics.
- Re-enable persona-scoped consumer groups only in dev; prod should not roll back after cutover.

## Observability

| Signal | Healthy |
|--------|---------|
| `cys_infrastructure_fallback_total{component="kafka_queue"}` | flat after cutover |
| Consumer group | `egregore-workers` only |
| DLQ `worker.jobs.dlq` | empty or investigated |

See [ARCHITECTURE.md](ARCHITECTURE.md) single-queue diagram.
