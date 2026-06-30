# Egregore Operator UI

Next.js operator console — lives at `ui/` inside the [egregore](..) repository.

See the [root README](../README.md) for full-stack local development (`make dev-infra`, `make dev-api`, `make dev-ui`).

## Quick start (UI only)

```bash
cd ui
cp .env.local.example .env.local
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). API must be running on `http://localhost:8080` (see root README).

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `NEXT_PUBLIC_EGREGORE_API_URL` | `http://localhost:8080` | Egregore API base URL |
| `NEXT_PUBLIC_EGREGORE_API_TOKEN` | — | Optional Bearer token when API auth is enabled |
| `NEXT_PUBLIC_LANGFUSE_HOST` | `http://localhost:3000` | Langfuse UI for job trace links |

## GUI vendor sync

See [docs/GUI_VENDOR.md](docs/GUI_VENDOR.md).

## Scripts

- `npm run dev` — development server
- `npm run build` — production build
- `npm run typecheck` — TypeScript check
- `npm run lint` — ESLint
