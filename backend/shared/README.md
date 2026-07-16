# egregore API

Python/uv backend for the egregore platform.

## Quick start

```bash
uv sync
cp .env.example .env   # optional: local secrets
USE_MEMORY_FALLBACK=true STAGE=test uv run egregore info
./scripts/pytest_batches.sh tests/architecture
```

Product personas and routing plans live in `agents/`. Operator UI is `../web_ui/`.

Python venv: `api/.venv` (after `uv sync`). Repo-wide cache cleanup: `make clean` from `../`.
