# Self-hosted Langfuse for egregore

Langfuse v3 stack for LLM trace observability (prompts, tool calls, latency, cost).

Operator UI runs on **:3000**; Langfuse uses **:3001** to avoid port conflicts.

## Prerequisites

- Docker Compose v2
- ~4 CPU / 16 GiB RAM recommended for dev
- All DB containers use **UTC** timezone (required by Langfuse)

## Quick start (recommended for dev)

From repo root:

```bash
make langfuse-dev-setup    # writes deploy/langfuse/.env + syncs projects/egregore/.env
make dev-langfuse-fresh    # reset volumes + headless init (org, project, API keys, user)
```

This uses [headless initialization](https://langfuse.com/self-hosting/administration/headless-initialization):

| Resource | Dev value |
|----------|-----------|
| UI | http://localhost:3001 |
| Login | `dev@egregore.local` / `egregore-dev` |
| Org | Egregore (`egregore`) |
| Project | `egregore-dev` |
| Public key | `pk-lf-egregore-dev-local` |
| Secret key | `sk-lf-egregore-dev-local` |

Keys are copied to `projects/egregore/.env` as `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST=http://localhost:3001`.

Restart API/worker after setup so they load the new env.

## Manual setup (UI)

If you prefer the UI instead of headless init:

1. `cd deploy/langfuse && cp env.example .env` — fill secrets, **comment out** `LANGFUSE_INIT_*` lines
2. `docker compose up -d`
3. Open http://localhost:3001 → **Sign up** (creates org + project)
4. Project → **Settings** → **API Keys** → Create
5. Copy keys to egregore `.env`

**Note:** Self-hosted Langfuse does not auto-create org/project on first visit — you must sign up or use `LANGFUSE_INIT_*`.

## API keys for egregore

Both keys are required (`langfuse_enabled` checks public + secret):

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3001   # not :3000 (Operator UI)
```

Verify:

```bash
USE_MEMORY_FALLBACK=true STAGE=test uv run egregore agent soc -i "langfuse smoke"
# → Langfuse UI → Traces
```

## Host ports

| Service   | Host port |
|-----------|-----------|
| Langfuse  | 3001      |
| Postgres  | 15432     |
| Redis     | 16379     |
| MinIO API | 9090      |

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Empty UI / no org | Run `make dev-langfuse-fresh` or sign up in UI |
| Org exists, no API keys | Create keys in project settings, or `make dev-langfuse-fresh` |
| JWT / session errors in logs | Clear browser cookies for localhost:3001 or use incognito; secrets may have changed |
| No traces in egregore | Check both keys in `.env`, `LANGFUSE_HOST=:3001`, restart worker/API |
| `DATABASE_URL` auth failed | Password must match `POSTGRES_PASSWORD` — `make langfuse-dev-setup` fixes this |

## Operations

```bash
make dev-langfuse          # start existing stack
make dev-langfuse-fresh    # wipe volumes + re-init (dev only)
docker compose -f deploy/langfuse/docker-compose.yml down
```

## References

- [Headless initialization](https://langfuse.com/self-hosting/administration/headless-initialization)
- [egregore observability runbook](../../docs/OBSERVABILITY.md)
