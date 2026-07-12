# Authz Grafana Panels

Add these PromQL queries to the Egregore dashboard when OpenFGA is enabled.

## Deny Rate

```promql
sum by (relation, object_type) (rate(cys_authz_deny_total[5m]))
```

## Check Error Rate

```promql
sum by (relation, object_type) (rate(cys_authz_error_total[5m]))
```

## p95 Check Latency

```promql
histogram_quantile(0.95, sum by (le, relation) (rate(cys_authz_check_latency_seconds_bucket[5m])))
```
