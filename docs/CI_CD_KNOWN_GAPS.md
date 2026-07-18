# CI/CD known gaps (release-gate.yml)

**Status: workflow-level resolved, GitHub-enforcement gap open** — all
`release-gate.yml` jobs are blocking *within the workflow* (the aggregate
`release-gate` job fails the whole run if any listed job doesn't succeed) as
of `feature/bypass-ci-lint` (Phase F complete). **Verified 2026-07-17 via
`gh api repos/{owner}/{repo}/rulesets` that this is not yet true at the
GitHub-enforcement layer**: `main` has no classic branch protection
(`GET .../branches/main/protection` → 404) and the one active ruleset
("Minimal Ruleset", ~DEFAULT_BRANCH) only enforces `deletion`,
`non_fast_forward`, GitHub-native `code_quality`, and GitHub-native
`code_scanning` (CodeQL alerts) — it has no `required_status_checks` rule
naming `release-gate` or any other job from this file. A PR can merge to
`main` today with every job in this workflow red. Adding that rule is a
live branch-protection change and needs an explicit decision (owner
confirmation, not an automated pass) before it's made.

## Resolved gates

| Job | Verification |
|-----|----------------|
| `lint` | matrixed over worker/api/tool-gateway/model-gateway (model-gateway added §49): `cd backend/<pkg> && uv run ruff check src tests && uv run ty check src` |
| `unit-tests` | matrixed over worker/api/tool-gateway/model-gateway (model-gateway added §49): `cd backend/<pkg> && ./scripts/pytest_batches.sh` |
| `linter-security` | matrixed over worker/api/tool-gateway/model-gateway (model-gateway added §49): `ruff check . --output-format sarif` + `gate-check.py --control linters`, reusable job |
| `arch-lint` | matrixed over worker/api/tool-gateway **only**: `make -C backend/<pkg> verify-architecture`. **Not** model-gateway — no import-linter config, no `scripts/verify_import_boundaries.py`, no `tests/architecture/` there yet (`docs/MICROSERVICES_SPLIT_PLAN.md` §49). |
| `domain-coverage` | `backend/contracts` was retired 2026-07-17 (`docs/MICROSERVICES_SPLIT_PLAN.md` §18) — `cys_core/domain` is now physically duplicated into `backend/worker`, `backend/api`, and (since the tool-gateway package extraction, §21.6) `backend/tool-gateway`, each with its own tests. The CI job (`release-gate.yml`'s `domain-coverage`) is matrixed over `[worker, api, tool-gateway]`, running inline per package: `pytest tests/domain/ -q --cov=src/cys_core/domain --cov-fail-under=100` — **no `--include` narrowing**, the 100% threshold applies to the *whole* `cys_core/domain` tree, independently in each package. There is a **separate, narrower** local convenience target, `make domain-gate` → `./scripts/pytest_batches.sh tests/domain --cov --domain-gate`, whose 100% threshold only covers `coverage report --include="src/cys_core/domain/{runs,catalog,observability}/*"` — also run per package now that each has its own physical copy. These remain two genuinely different checks — the Makefile target is a local dev convenience, not what blocks merges. `model-gateway` has its own small `cys_core/domain/security/*` tree but no `tests/domain/` directory yet, so it's **not** in this matrix (`docs/MICROSERVICES_SPLIT_PLAN.md` §49). |
| `adversarial` | `pytest tests/adversarial/ -m adversarial` (0 xfail), matrixed over worker/api/tool-gateway **only** — model-gateway has no `tests/adversarial/` yet (§49). |
| `secret-scan` / `sast` / `osa` | security scanners + `gate-check.py`. `sast`'s CodeQL now scans `backend/model-gateway/src` too (`.github/codeql/codeql-config.yml`, added §49.2 — it was missing from this include-list since model-gateway was built). |
| `iac-scan` / `dockerfile-lint` / `skill-scanner` | reusable scanner jobs |

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
