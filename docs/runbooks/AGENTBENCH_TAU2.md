# AgentBench & Tau2 eval runbook

Skeleton adapters live in `cys_core.application.eval.adapters`.

## Smoke

```bash
cd projects/egregore
uv run python -c "
from cys_core.application.eval.adapters import AgentBenchAdapterSkeleton, Tau2AdapterSkeleton
print(AgentBenchAdapterSkeleton().db_lite_score())
print(Tau2AdapterSkeleton().mock_domain_pass())
"
```

## AgentBench-lite

| Case | Method | Purpose |
|------|--------|---------|
| DB lite | `db_lite_score` | SQL/tool trajectory |
| Trace map | `map_trace_steps` | Langfuse step alignment |

## Tau2 domains

| Domain | Method |
|--------|--------|
| mock | `mock_domain_pass` |
| retail | `retail_domain_pass` |
| banking | `banking_knowledge_pass` |

## Local traces

```bash
LANGFUSE_BASE_URL=http://localhost:3001 ./scripts/k8s/langfuse-benchmark-report.sh
```

See also [OBSERVABILITY.md](../OBSERVABILITY.md) for trace path matrix.
