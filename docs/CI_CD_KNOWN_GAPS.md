# CI/CD known gaps (release-gate.yml)

Tracks every control `release-gate.yml` runs but does not yet block merge on
(`continue-on-error: true`), and every adversarial test marked `xfail`, so the
warn-only/xfail state is a deliberate, tracked decision — not a silently
lowered bar. Flip each item to blocking/un-xfail once its root cause is fixed.

## Warn-only jobs

### `lint` — 367 pre-existing ruff findings

`uv run ruff check src tests` — the
exact command `ci.yml`'s own (now-superseded) `lint` job used — currently
reports 367 findings (284 auto-fixable with `ruff check --fix`, 9 more with
`--unsafe-fixes`). Since every other job in `ci.yml` had `needs: [lint]`,
this means that pipeline has likely never gotten past its first job. Not
fixed here: a blanket repo-wide `--fix` is a large, unrelated diff that
doesn't belong bundled into the PR that introduces this gate. `ty check`
(the type checker) was not independently re-verified.

### `unit-tests` — ~60 pre-existing test failures

`./scripts/pytest_batches.sh` currently fails in ~15 of 29 batches, unrelated
to any single recent change (confirmed the same night via git-stash
bisection against a specific 5-file diff). Root cause not yet triaged in
detail; hypothesized to be fallout from the `bootstrap` Container-splitting
refactor (see the `bootstrap/__init__.py` shadowing footgun noted below —
plausibly not the only such landmine it left behind).

### `arch-lint` — import-boundary violations

`uv run lint-imports` currently reports real violations predating this
workflow: `bootstrap` imported directly from `cys_core.domain` (4 files) and
`cys_core.application` (8 files), plus `cys_core.infrastructure` imported
directly from `interfaces/api` in 3 files (`engagements.py`, `follow_ups.py`,
`work_orders.py`). This also breaks `tests/architecture/test_layer_contracts.py`'s
shrink-only allowlist contract (`ALLOWLIST_BOOTSTRAP_INTERFACES` grew to 40,
ceiling is 38) — a regression against the state `ARCHITECTURE_DEBT.md`'s
Phase 7/8 remediation had left green. See that file for the full layering
model; this is the up-to-date "still broken" pointer.

Fix means routing `Settings`/infra access through the container/ports instead
of importing `bootstrap`/`infrastructure` inline, consistent with the Wave
A–E pattern already used elsewhere in the codebase.

### `domain-coverage` — 100% target, ~78% actual

`src/cys_core/domain` coverage gate is set to `--cov-fail-under=100` but current
coverage is ~78%. Whole files are at 0% (e.g. `workers/continuation.py`,
`workspace/models.py`). Aspirational target predates this workflow; needs
either a real push to 100% or a documented, intentional ratchet baseline
instead of an unenforced 100% that nothing has met.

## xfailed adversarial tests

### `tests/adversarial/test_skill_injection.py` (3 tests)

`load_skill()` (`src/cys_core/infrastructure/skill/load_skill.py`) was refactored
to a dynamic-catalog/allowlist model (`profile_id`, `staging_status`,
`get_input_sanitizer()`) and no longer accepts a `registry` argument or does
`content_hash` verification. The hash-pinning / unsigned-skill-rejection
behavior these tests assert appears to have been **dropped, not renamed** —
there is no hash-mismatch check left in the new code path at all. This needs
a product/security decision: reinstate an equivalent control, or consciously
retire these tests with a documented replacement mechanism. Do not un-xfail
by weakening the assertions.

### `tests/adversarial/test_dow_budget.py::test_gateway_blocks_high_risk_tool_chain`

Settings mocking was fixed to actually reach `Container.__init__` (previous
failure was `bootstrap/__init__.py`'s `settings` singleton re-export shadowing
the `bootstrap.settings` submodule attribute — see inline comment in the
test), but the invoke chain still succeeds on the 2nd call instead of being
blocked at `max_high_risk_tool_chain_depth=1`. Either
`bootstrap/containers/tools_container.py`'s `ToolChainPolicy` construction, or
`get_tool_chain_policy()`, isn't re-reading settings after the container
reset. Needs tracing before un-xfailing.

## Infra fixes applied while first bringing the gate up

- **`release-gate.yml` never ran a single job** (`startup_failure`, 0 jobs
  created, on every push) until this was found: `job-sast.yml`'s `codeql`
  job requests `permissions: actions: read` at the job level, but the
  caller (`release-gate.yml`) never granted `actions` at its top-level
  `permissions:` block. A reusable workflow's job cannot request a
  permission scope its caller doesn't hold — GitHub rejects the *entire*
  run at validation time when that happens, before any job (even unrelated
  ones) is created, which is what made this so hard to isolate. Fixed by
  adding `actions: read` to `release-gate.yml`'s top-level permissions.
- **`osa / trivy-fs`**: pinned to `aquasecurity/trivy-action@0.28.0`, a tag
  that doesn't exist. Bumped to `v0.36.0` (also fixed in `job-sca-image.yml`,
  used by the main-only container-scan job).
- **`sast / semgrep`, and by the same pattern `iac-scan` / `linter-security`**:
  the fallback SARIF these jobs write when the real scanner produces no
  file — `{"runs":[{"results":[]}]}` — isn't schema-valid SARIF (no
  `version`, no `tool`), so `codeql-action/upload-sarif` rejects it whenever
  that fallback triggers. Replaced with a minimal valid SARIF document in
  the 3 files release-gate.yml actually calls. The same broken placeholder
  still exists in ~8 other workflow files not in this PR's call graph
  (`job-ml-model-scan.yml`, `nightly-sast.yml`, the `job-oss-*` variants,
  etc.) — same fix, just out of scope tonight.
- **`osa / dependency-review`** still fails: `Dependency review is not
  supported on this repository. Please ensure that Dependency graph is
  enabled` — a repo setting (Settings → Security → Dependency graph), not
  a code fix. Left for a human to enable; not something to toggle
  unilaterally from an agent session.
- **`sast / codeql` was silently reporting `findings=0` on every run despite
  CodeQL genuinely finding 3 real `py/path-injection` results** (see
  "Real finding" below) — the single worst bug found tonight, because it
  made the SAST gate decorative rather than blocking. `codeql-action/analyze`
  writes its SARIF to `$RUNNER_WORKSPACE/results/<language>.sarif` (one
  directory *above* the checkout) by default; the gate-check step was
  checking the relative path `results/python.sarif` (*inside* the
  checkout) — never matched, so it silently fell through to the empty
  placeholder and always passed. Fixed by pinning `analyze`'s `output:` to
  a known path (`codeql-sarif/`) and — more importantly — changed the
  gate-check step to **fail loudly if the real report is missing**,
  instead of silently substituting an empty one. Same audit found
  `job-linter-security.yml` gating its real `ruff` scan behind
  `$ENABLE_REAL_LINTERS`, an env var that can never reach it (the same
  `env:`-doesn't-propagate-into-`uses:` limitation noted for
  `SECURITY_POLICY` above) — it was defaulting to `false` and always
  writing the empty stub. Now always runs the real scan.
  `job-dockerfile-lint.yml`'s gate-check step is *still* purely decorative
  (`echo '{"runs":[{"results":[]}]}' > hadolint.sarif` runs unconditionally,
  never reads hadolint's actual output) — not fixed here since
  `hadolint-action` itself still fails the job on real findings via its own
  exit code and this control is warn-only, but the gate-check step's own
  verdict should not be trusted.
- **Real finding, not fixed here**: CodeQL flagged `py/path-injection`
  (severity: error) three times in
  `cys_core/infrastructure/runs/attachment_store.py` (now at
  `src/cys_core/infrastructure/runs/attachment_store.py`), lines 24/26/27 —
  `tenant_id` and `run_id` go straight into `Path` construction with no
  sanitization, unlike `filename` which already goes through
  `_safe_filename()`. Both values originate from
  `interfaces/api/runs.py`'s `upload_attachment` (`run_id` from the URL
  path, `tenant_id` from the request). This is a real, unaddressed path
  traversal risk — surfaced by this PR's SAST fix, deliberately not fixed
  in the same PR as the CI/CD mechanism itself so the fix gets its own
  reviewable diff. Do this next.

## Note for future readers

`bootstrap/__init__.py` does `from bootstrap.settings import Settings,
get_settings, settings` — that last import binds a `settings` singleton
**instance** onto the `bootstrap` package's own namespace, which shadows the
`bootstrap.settings` submodule reference Python would otherwise set there
automatically. Any dotted-string `monkeypatch.setattr("bootstrap.settings.x",
...)` or `import bootstrap.settings as x` (which also resolves via attribute
access, not `sys.modules`) will silently hit the singleton instead of the
module. Use `importlib.import_module("bootstrap.settings")` or patch the
actual call site's own `from ... import get_settings` binding instead.
