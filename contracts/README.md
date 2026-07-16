# Contract snapshots

Vendored artifacts used by contract tests in `backend/contracts/tests/contracts/`. These files are **not** deployed from this repo directly; they mirror upstream cxado manifests so CI can run without the meta-repo checkout.

## Kafka / Redpanda topics

| Snapshot | Upstream source |
|----------|-----------------|
| `k8s/cxado-offline/15-redpanda-topics-job.yaml` | `deploy/k8s/cxado-offline/15-redpanda-topics-job.yaml` in [cxado/cys_framework](https://github.com/butbeautifulv/cys_framework) |

### Refresh procedure

1. Diff the upstream job against this snapshot:
   ```bash
   diff deploy/k8s/cxado-offline/15-redpanda-topics-job.yaml \
     projects/egregore/contracts/k8s/cxado-offline/15-redpanda-topics-job.yaml
   ```
   (paths relative to cxado meta-repo root)
2. If topics, partition counts, or topic names changed, copy the upstream file and restore the header comment on line 1.
3. Run `cd backend/contracts && uv run pytest tests/contracts/test_kafka_topics_k8s.py -q`
4. Commit with message `test(contracts): refresh redpanda topics snapshot`

Commit snapshot updates whenever platform topic layout changes or egregore's `WORKER_JOBS_TOPIC` constant is updated.
