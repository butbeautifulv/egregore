# CI/CD known gaps (release-gate.yml)

**Status: resolved** — all `release-gate.yml` jobs are blocking as of
`feature/bypass-ci-lint` (Phase F complete). Require the aggregate
`release-gate` check in branch protection.

## Resolved gates

| Job | Verification |
|-----|----------------|
| `lint` | matrixed over contracts/worker/api: `cd backend/<pkg> && uv run ruff check src tests && uv run ty check src` |
| `unit-tests` | matrixed over contracts/worker/api: `cd backend/<pkg> && ./scripts/pytest_batches.sh` |
| `arch-lint` | matrixed over contracts/worker/api: `make -C backend/<pkg> verify-architecture` |
| `domain-coverage` | `backend/contracts` only, via `make domain-gate` → `./scripts/pytest_batches.sh tests/domain --cov --domain-gate`. The 100% threshold applies only to `coverage report --include="src/cys_core/domain/{runs,catalog,observability}/*"` — **not** all of `cys_core/domain` (e.g. `domain/engagement/*` is not in scope). See `scripts/pytest_batches.sh`'s `--domain-gate` branch for the authoritative `--include` list. |
| `adversarial` | `pytest tests/adversarial/ -m adversarial` (0 xfail) |
| `secret-scan` / `sast` / `osa` | security scanners + `gate-check.py` |
| `iac-scan` / `dockerfile-lint` / `linter-security` / `skill-scanner` | reusable scanner jobs |

## Historical notes (infra fixes during gate bring-up)

Archived for Kaizen reference — not open gaps:

- `release-gate.yml` needed `permissions.actions: read` for reusable CodeQL workflow.
- Trivy action tag `0.28.0` → `v0.36.0`.
- SARIF fallback placeholders replaced with schema-valid minimal documents.
- CodeQL SARIF path + severity handling documented in commit history on this branch.
- `attachment_store.py` path-injection fix + regression test.
- `langsmith` / `starlette` dependency bumps for OSA HIGH findings.

## IaC Checkov triage (`iac-scan`)

Scope: `deploy/` only, frameworks `helm` + `dockerfile` (see `.github/workflows/job-iac-scan.yml`). Out of scan: `api/`, `web_ui/`, `docs/`; UI image Dockerfile is covered by the separate `web-ui` / `dockerfile-lint` jobs.

Baseline skips in [`.checkov.yaml`](../.checkov.yaml):

| Rule | Reason |
|------|--------|
| `CKV_K8S_21` | Namespace set at `helm install -n` |
| `CKV_K8S_35` | Secrets via `envFrom` + external Secret/ConfigMap |
| `CKV_K8S_14` / `CKV_K8S_15` / `CKV_K8S_43` | Image tag, pull policy, and digest from deploy-time values (Nexus/Kaniko loop) |
| `CKV2_K8S_6` | NetworkPolicy enforced at platform/nginx ingress layer, not in chart |

`deploy/Dockerfile.corp.api` / `deploy/Dockerfile.corp.worker` excluded via `skip-path` (offline Kaniko lifecycle).

Helm templates harden pod/container `securityContext` and UI probes (commits on `feature/bypass-ci-lint`). Local smoke:

```bash
checkov -d deploy --framework helm,dockerfile --config-file .checkov.yaml --soft-fail \
  --output sarif --output-file-path reports/checkov.sarif
python scripts/gate-check.py --control iac --report reports/checkov.sarif \
  --policy config/security-gate-policy.yaml
```

## Note for future readers

`bootstrap/__init__.py` re-exports `settings` singleton and shadows the
`bootstrap.settings` submodule — patch `get_settings` at the call site or use
`importlib.import_module("bootstrap.settings")` in tests.
