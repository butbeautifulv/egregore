# Development guide

Local workflows for egregore API, worker, Operator UI, and observability stacks.

## Prerequisites

```bash
uv sync
cp .env.example .env
docker compose up -d   # Postgres, Redis, Redpanda, Qdrant
uv run egregore migrate
```

See [README.md](../README.md) for full quick start and [OBSERVABILITY.md](OBSERVABILITY.md) for Langfuse, Prometheus, Grafana, and Tempo.

## Dev stack

One command (infra + supervised API + 2 workers + UI):

```bash
make dev
```

Or step by step:

```bash
make dev-infra       # core infra
make dev-langfuse    # Langfuse UI http://localhost:3001
make dev-obs         # Prometheus :9091, Grafana :3002, Tempo OTLP :4317
make dev-api         # API http://localhost:8080
make dev-workers     # 2 worker daemons (WORKER_REPLICAS, never idle-exit)
make dev-ui          # Operator UI http://localhost:3000
```

`make dev` and `scripts/dev.sh` start API + `WORKER_REPLICAS` workers (default 2) with auto-restart on crash. Workers use `WORKER_IDLE_TIMEOUT=0` (run until stopped). Docker: `make dev-docker` scales workers the same way.

## Veil knowledge MCP (playbooks + graph)

When [Veil knowledge](https://github.com/butbeautifulv/veil) is running locally (Graph API `:8090`, MCP HTTP `:8091`), egregore workers can call read-only playbook and threat-intel tools.

Prerequisites:

```bash
# Veil stack (from projects/veil) — GRAPH_PACK_SKIP=1 on restart if graph already in Neo4j
curl http://localhost:8090/health
curl http://localhost:8091/health
```

In `projects/egregore/.env`:

```bash
VEIL_MCP_URL=http://localhost:8091/mcp
VEIL_MCP_ENABLED=true
USE_TOOL_GATEWAY=false
# Optional: route tools via gateway (requires `make dev-tool-gateway` on :8092)
# USE_TOOL_GATEWAY=true
# TOOL_GATEWAY_URL=http://localhost:8092
```

Start the egregore tool gateway (optional separate terminal):

```bash
make dev-tool-gateway
```

Personas with Veil tools: `consultant`, `soc`, `network`, `compliance` — see `agents/personas/*/agent.yaml` (`playbook_search`, `ti_search_in_category`, …).

Smoke:

```bash
USE_MEMORY_FALLBACK=true STAGE=test uv run pytest tests/tool_gateway/test_veil_mcp_adapter.py -q
```

## Local LLM (Ollama / OpenAI-compatible)

egregore routes all model calls through LiteLLM. For local inference without cloud API keys, point at Ollama or any OpenAI-compatible endpoint.

### Ollama

```bash
# Terminal 1 — start Ollama and pull a model
ollama serve
ollama pull llama3.2
```

In `projects/egregore/.env`:

```bash
LLM_PROVIDER=litellm
LLM_MODEL=ollama/llama3.2
LLM_BASE_URL=http://localhost:11434
LLM_TEMPERATURE=0.1
USE_MEMORY_FALLBACK=true
STAGE=dev
```

Cloud API keys (`ANTHROPIC_API_KEY`, etc.) can stay empty for Ollama.

### vLLM / other OpenAI-compat servers

Use the provider prefix LiteLLM expects (e.g. `openai/Qwen3.6-27B-NVFP4`) and set `LLM_BASE_URL` to the server `/v1` base URL. Model id must match `GET /v1/models`.

```bash
LLM_PROVIDER=litellm
LLM_MODEL=openai/Qwen3.6-27B-NVFP4
LLM_BASE_URL=http://10.8.185.186:11612/v1
LLM_TEMPERATURE=0.1
```

Cloud API keys can stay empty — when `LLM_BASE_URL` is set, egregore passes a dummy key for local OpenAI-compatible servers.

## Verify prompts reach the LLM

Use this checklist when jobs appear to hang or traces are empty.

### 1. Direct agent smoke (no queue)

```bash
USE_MEMORY_FALLBACK=true STAGE=test uv run egregore agent soc -i "test prompt"
```

Success: JSON stdout without `"error"`. With Ollama running, `ollama serve` logs an HTTP completion request.

### 2. Full worker path

```bash
USE_MEMORY_FALLBACK=true STAGE=test uv run egregore ingest -t siem.alert -p '{"alert":"obs-test"}'
USE_MEMORY_FALLBACK=true STAGE=test uv run egregore worker --once
```

### 3. LiteLLM debug logging

```bash
LITELLM_LOG=DEBUG USE_MEMORY_FALLBACK=true uv run egregore agent soc -i "test"
```

### 4. Langfuse traces

1. `make dev-langfuse` and create API keys in http://localhost:3001
2. Set `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST=http://localhost:3001` in `.env`
3. Run ingest + `worker --once` (or `worker --daemon`)
4. Open Langfuse → Traces; filter by tag `persona:soc`

Worker daemon flushes Langfuse after each processed job so traces appear without waiting for process exit.

### 5. Prometheus metrics

```bash
make dev-obs
make dev-api
curl -s localhost:8080/metrics | grep cys_events_ingested
```

After `ingest`, `cys_events_ingested_total` should increase. Grafana: http://localhost:3002 (admin / admin).

## OpenTelemetry (optional)

```bash
make dev-obs
OTEL_ENABLED=true uv run egregore serve --port 8080
```

HTTP spans export to Tempo on `localhost:4317`. Explore in Grafana → Tempo. LLM detail stays in Langfuse.

## Common issues

| Symptom | Fix |
|---------|-----|
| `{"error": ...}` from agent | Set `LLM_MODEL` + `LLM_BASE_URL` for local model, or add cloud API key |
| UI «Starting…» forever / API hangs minutes | `manual.investigation` planner used to block HTTP until LLM returned; now API returns **202** when `MANUAL_INVESTIGATION_ASYNC=true`. Check `GET /investigations/{id}` → `planner_status` |
| Langfuse `Connection error` on planner traces | vLLM unreachable or slow; set `LLM_REQUEST_TIMEOUT=120` (default). ERROR ~400s = old litellm default; after fix, fallback in ~2 min |
| Langfuse DEFAULT generation 170–240s | Model is up but slow (local Qwen); workers enqueue after planner completes in background |
| No Langfuse traces | Both `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` required |
| Jobs never run | Workers must be running (`make dev`); postgres + redis healthy (`docker compose ps`) |
| Port 3000 in use | Operator UI uses **3000**; Langfuse uses **3001** |
| UI dev `ENOSPC` | `cd ui && bunx next dev --webpack` or `bun run build && bun run start` |

### Langfuse trace diagnosis

Filter traces by tag `persona:planner`:

| Observation | Meaning |
|-------------|---------|
| `GENERATION` level ERROR, `Connection error`, latency ~400s | vLLM was down; litellm retried until connect failed (before `LLM_REQUEST_TIMEOUT`) |
| `GENERATION` level DEFAULT, latency 170–240s, JSON in output | Planner succeeded; jobs enqueue in background (async API) or after HTTP response (sync CLI) |
| `rationale: planner_unavailable_fallback` in worker payload | Planner failed; default personas `soc,network,compliance` used |

Preflight before investigations:

```bash
curl -m 5 -H "Authorization: Bearer EMPTY" "${LLM_BASE_URL%/}/models"
docker compose ps postgres redis
```

## CI

Local gates mirror GitHub Actions (`.github/workflows/ci.yml`):

```bash
make test-batches           # all pytest batches
make domain-gate            # 100% coverage on cys_core/domain/{runs,catalog,observability}
make verify-architecture    # no langfuse in core + import boundaries
make arch-gate              # tests/architecture batch
make verify-import-boundaries
```

CI jobs: `lint` (ruff), `unit-batches`, `domain-gate`, `verify-architecture`, `arch-gate`, plus Fabrica security gates via `security-shift-left.yml` (B1–B6).

Required on PR: `arch-gate`, `adversarial-gate`, `agent-policy-gate`, `security-shift-left`.
