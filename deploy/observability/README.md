# Dev observability stack (Prometheus + Grafana + Tempo)

Local metrics and trace backend for egregore development.

## Start

```bash
# from repo root
make dev-obs

# or
docker compose -f deploy/observability/docker-compose.yml up -d
```

## Endpoints

| Service | URL | Notes |
|---------|-----|-------|
| Prometheus | http://localhost:9091 | Scrape config in `prometheus/prometheus.yml` |
| Grafana | http://localhost:3002 | login `admin` / `admin` |
| Tempo | http://localhost:3200 | Trace query API |
| Tempo OTLP | localhost:4317 | gRPC ingest when `OTEL_ENABLED=true` |

Run `make dev-api` (or `uv run egregore serve`) on the host so Prometheus can reach `/metrics`.

Optional tool gateway (not auto-started): `make dev-tool-gateway` → `:8092/metrics`. Enable routing in `.env` only when needed: `USE_TOOL_GATEWAY=true`.

## Prometheus scrape jobs

| Job | Target | Purpose |
|-----|--------|---------|
| `prometheus` | `localhost:9090` | Self-monitoring |
| `egregore-api` | `host.docker.internal:8080/metrics` | Ingress + in-process worker metrics |
| `egregore-tool-gateway` | `host.docker.internal:8092/metrics` | MCP tool gateway (when running) |
| `tempo` | `tempo:3200/metrics` | Trace backend health |
| `grafana` | `grafana:3000/metrics` | Grafana self-metrics |

After editing `prometheus/prometheus.yml`:

```bash
make obs-reload
# or restart: docker compose -f deploy/observability/docker-compose.yml restart prometheus
```

Check targets: http://localhost:9091/targets

## Grafana dashboard

Auto-provisioned from `deploy/grafana/dashboards/cys-agi.json` (folder **Egregore**).

Panels cover all `cys_*` metrics: events, workers, tools, sanitizer, HITL, RAG, memory, DoW cost, trust scores, and scrape target health.

To force dashboard refresh after JSON edit, restart Grafana:

```bash
docker compose -f deploy/observability/docker-compose.yml restart grafana
```

## Stop

```bash
docker compose -f deploy/observability/docker-compose.yml down
```
