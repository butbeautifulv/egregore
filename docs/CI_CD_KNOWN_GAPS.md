# CI/CD known gaps (release-gate.yml)

Tracks every control `release-gate.yml` runs but does not yet block merge on
(`continue-on-error: true`), and every adversarial test marked `xfail`, so the
warn-only/xfail state is a deliberate, tracked decision — not a silently
lowered bar. Flip each item to blocking/un-xfail once its root cause is fixed.

## Warn-only jobs

### ~~`lint`~~ — **resolved** (blocking since feature/bypass-ci-lint)

`uv run ruff check src tests` and `uv run ty check src` both exit 0. `noqa`
suppressions removed; ty protocol alignment on `AgentRuntime.arun` /
`PlannerRuntime`. Lint job `continue-on-error` removed from `release-gate.yml`.

### ~~`unit-tests`~~ — **resolved** (blocking since feature/bypass-ci-lint)

Post-arch-refactor regressions fixed: `runtime_config` defaults,
monkeypatch targets for container/`get_follow_up_plan_enabled`/
`get_egress_streaming_settings`, and related test wiring. All 29 pytest
batches green (`./scripts/pytest_batches.sh` exits 0). `continue-on-error`
removed from `unit-tests` job in `release-gate.yml`.

### ~~`arch-lint`~~ — **resolved** (blocking since feature/bypass-ci-lint)

`make -C api verify-architecture` exits 0: `lint-imports` (3 contracts
kept), `verify_import_boundaries.py`, `verify_no_langfuse_in_core.sh`, and
`tests/architecture/` all green. `continue-on-error` removed from `arch-lint`
job in `release-gate.yml`.

### `domain-coverage` — resolved (100% on `src/cys_core/domain`)

`tests/domain/` with `--cov=src/cys_core/domain --cov-fail-under=100` exits 0.
`continue-on-error` removed from `domain-coverage` job in `release-gate.yml`.

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
- **`osa / dependency-review`**: was failing with `Dependency review is not
  supported on this repository. Please ensure that Dependency graph is
  enabled` — a repo setting (Settings → Security → Dependency graph), not a
  code fix. Enabled by a human mid-session; not something toggled
  unilaterally from an agent session.
- **`sast / codeql` was silently reporting `findings=0` on every run despite
  CodeQL genuinely finding 3 real `py/path-injection` results** — the
  single worst bug found tonight, because it made the SAST gate decorative
  rather than blocking.
  - Root cause #1: `codeql-action/analyze` writes its SARIF to
    `$RUNNER_WORKSPACE/results/<language>.sarif` (one directory *above*
    the checkout) by default; the gate-check step checked the relative
    path `results/python.sarif` (*inside* the checkout) — never matched,
    silently fell through to an empty placeholder, always passed. Fixed by
    pinning `analyze`'s `output:` to a known path (`codeql-sarif/`) and
    changing the gate-check step to **fail loudly if the real report is
    missing** instead of silently substituting one.
  - Root cause #2, found *after* fixing #1: the local SARIF `analyze`
    writes has **no severity information in it at all** —
    `tool.driver.rules` is an empty array and `results[].level` is
    entirely absent (confirmed by dumping the raw file's structure in CI).
    GitHub only attaches `rule.defaultConfiguration.level` /
    `security-severity` server-side, after ingesting the upload. No amount
    of local JSON parsing can recover severity that structurally isn't in
    the file gate-check.py reads.
  - Tried fixing #2 by querying the Code Scanning Alerts API instead
    (`GET /repos/{repo}/code-scanning/alerts`, which does have real
    `rule.security_severity_level`) — but it consistently returned **0
    alerts** even for commits where `/code-scanning/analyses` confirmed 3
    real results were uploaded and fully processed
    (`analysis upload status is complete`). Didn't chase this further
    (possibly branch/ref-association timing, possibly something else) —
    shipping an unverified "fix" here risks silently reintroducing exactly
    the same failure mode via a different path.
  - **Final state**: any CodeQL finding blocks the job (no severity
    grading). Coarser than the policy's intended `severity_block:
    [critical, high]`, but it can no longer silently pass a real
    vulnerability. File:line + rule + message are printed to the job log
    for every finding either way. Proper severity-aware CodeQL gating is
    real follow-up work — start from why the Alerts API showed 0 results.
  - Same audit found `job-linter-security.yml` gating its real `ruff` scan
    behind `$ENABLE_REAL_LINTERS`, an env var that can never reach it (the
    same `env:`-doesn't-propagate-into-`uses:` limitation noted for
    `SECURITY_POLICY` above) — it was defaulting to `false` and always
    writing the empty stub. Now always runs the real scan.
  - `job-dockerfile-lint.yml`'s gate-check step is *still* purely
    decorative (`echo '{"runs":[{"results":[]}]}' > hadolint.sarif` runs
    unconditionally, never reads hadolint's actual output) — not fixed
    here since `hadolint-action` itself still fails the job on real
    findings via its own exit code and this control is warn-only, but the
    gate-check step's own verdict should not be trusted.
- **`osa / trivy-fs`**: correctly found 2 real HIGH-severity dependency
  vulnerabilities (`langsmith` 0.8.5, GHSA-f4xh-w4cj-qxq8; `starlette`
  1.3.0, CVE-2026-54283) among 18 total findings (the other 16 are
  medium/low/unknown — `severity: CRITICAL,HIGH` on the trivy-action step
  controls trivy's own reporting threshold, not what ends up in the SARIF,
  so lower-severity findings still show up for visibility). This gate was
  working correctly. Fixed via `uv lock --upgrade-package langsmith
  --upgrade-package starlette` (langsmith → 0.10.5, starlette → 1.3.1).
  Added a "Print findings" step so future runs show file/rule/severity
  directly in the job log instead of only a pass/fail count.
- **Real finding, fixed**: CodeQL's `py/path-injection` in
  `src/cys_core/infrastructure/runs/attachment_store.py` — `tenant_id` and
  `run_id` went straight into `Path` construction with no sanitization,
  unlike `filename` which already went through `_safe_filename()`. Both
  values originate from `interfaces/api/runs.py`'s `upload_attachment`
  (`run_id` from the URL path, `tenant_id` from the request body). Fixed
  with `_safe_path_segment()`, the same character-allowlist approach
  already used for filenames, plus a regression test. Note: CodeQL's own
  taint tracker does *not* recognize this custom sanitizer as a valid
  taint barrier and keeps flagging the same data flow — a known class of
  CodeQL limitation (custom sanitizers need explicit query-model
  annotations to be recognized); the runtime behavior is fixed and tested,
  even though CodeQL will likely keep reporting it until that's addressed
  too, which is part of why "any finding blocks" (see above) needs
  triage-and-dismiss workflow, not blind trust, once enabled.

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
