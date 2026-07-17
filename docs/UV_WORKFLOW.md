# uv workflow for refactor PRs (Stream F py-22)

Run from `projects/egregore/`.

## Local gate (before PR)

```bash
./scripts/refactor_checks.sh
```

Equivalent manual steps:

```bash
uv lock --check
uv run ruff check .
uv run python scripts/verify_import_boundaries.py
./scripts/pytest_batches.sh tests/architecture tests/contracts
./scripts/pytest_batches.sh tests/infrastructure tests/application tests/api tests/worker
```

## Targeted batches during development

```bash
./scripts/pytest_batches.sh tests/infrastructure -- -k kafka
./scripts/pytest_batches.sh tests/application tests/api
```

## Environment

```bash
export STAGE=test
export USE_MEMORY_FALLBACK=true
```

## CI alignment

| Gate | Command |
|------|---------|
| Import boundaries | `uv run python scripts/verify_import_boundaries.py` |
| Architecture | `./scripts/pytest_batches.sh tests/architecture tests/arch` |
| Domain coverage (run per package — worker and api each own a physical copy) | `./scripts/pytest_batches.sh --cov --domain-gate` |

See also [PYTHON_RUNTIME_HARDENING.md](PYTHON_RUNTIME_HARDENING.md) and [CATALOG_SEED.md](CATALOG_SEED.md).
