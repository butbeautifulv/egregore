# CI/CD known gaps (release-gate.yml)

**Status: resolved** — all `release-gate.yml` jobs are blocking as of
`feature/bypass-ci-lint` (Phase F complete). Require the aggregate
`release-gate` check in branch protection.

## Resolved gates

| Job | Verification |
|-----|----------------|
| `lint` | `cd api && uv run ruff check src tests && uv run ty check src` |
| `unit-tests` | `cd api && ./scripts/pytest_batches.sh` (29/29 batches) |
| `arch-lint` | `make -C api verify-architecture` |
| `domain-coverage` | `pytest tests/domain/ --cov=src/cys_core/domain --cov-fail-under=100` |
| `adversarial` | `pytest tests/adversarial/ -m adversarial` (0 xfail) |
| `secret-scan` / `sast` / `osa` | security scanners + `gate-check.py` |

Warn-only jobs (`iac-scan`, `dockerfile-lint`, `linter-security`, `skill-scanner`)
still run on every PR but are excluded from the `release-gate` aggregate `needs`.

## Historical notes (infra fixes during gate bring-up)

Archived for Kaizen reference — not open gaps:

- `release-gate.yml` needed `permissions.actions: read` for reusable CodeQL workflow.
- Trivy action tag `0.28.0` → `v0.36.0`.
- SARIF fallback placeholders replaced with schema-valid minimal documents.
- CodeQL SARIF path + severity handling documented in commit history on this branch.
- `attachment_store.py` path-injection fix + regression test.
- `langsmith` / `starlette` dependency bumps for OSA HIGH findings.

## Note for future readers

`bootstrap/__init__.py` re-exports `settings` singleton and shadows the
`bootstrap.settings` submodule — patch `get_settings` at the call site or use
`importlib.import_module("bootstrap.settings")` in tests.
