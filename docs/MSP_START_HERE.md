# Start here

Read in this order:

1. **[`MICROSERVICES_SPLIT_PLAN.md`](MICROSERVICES_SPLIT_PLAN.md)** — current state, remaining work.
   Strict to-do list, no narrative.
2. **[`MSP_BACKLOG.md`](MSP_BACKLOG.md)** — full history. Every "done" item, every bug found and how
   it was actually fixed, every deferred decision and why. If something in the plan references a
   `§N`, that's a section in this file. Before touching a package, grep the backlog for its name —
   the reasoning behind why something looks the way it does usually lives there, not in a code
   comment.
3. This file — what tends to go wrong in this project and why, so it doesn't need to be
   re-discovered every session.

Never claim something is done, fixed, or verified without having actually run the check and read
the real result (CI run conclusion, not just "dispatched"; test/script output, not just "should
work"). This project's standing rule is: dispatch CI in the background and keep working, but the
*claim* of "verified" requires reading the real result first.

---

## Reflection: recurring problems, root causes, fixes

Five patterns that have each caused a real, confirmed incident more than once in this project's
history. Each below: the pattern, five-whys to its structural root cause, and five fixes (one per
level, cheapest/most-immediate first, most structural last).

### 1. Fixes applied to one physical copy of a duplicated package, not synced to its siblings

This codebase deliberately duplicates `cys_core.domain`/`bootstrap`/generic infra across six
backend packages instead of sharing one (`§18`) — a real, load-bearing decision (see the working
convention below), not an oversight. But it means every fix has to be applied N times, and it's easy
to forget one. Confirmed instances: `§39`'s RAG fail-closed fix wasn't synced to `worker` until
`§43.3` caught it; `§52`'s tool-gateway async fix needed a whole follow-up entry (`§53`) just to
sync it to `worker`/`agent-runtime`; `§55` explicitly notes a fix "deliberately not synced this
pass."

1. Why does a fix land in one package and not its siblings? Because the fix is written and verified
   against the one package where the bug was found or the feature was needed, and nothing forces a
   second look at the other five.
2. Why doesn't anything force that second look? Because there's no tooling that diffs the
   "supposed to be identical" files across packages and flags drift — the only enforcement is a
   written convention ("grep for other packages' copies before calling a fix done") that depends on
   remembering to apply it.
3. Why is enforcement just a written convention? Because duplication was a deliberate, recent
   architectural choice (undoing a shared `contracts` package, `§18`/`§21.6`) — the tooling to keep
   duplicates honest wasn't built in the same pass as the decision to duplicate.
4. Why wasn't that tooling built at the same time? Because the immediate goal of the split was
   physical independence (no shared package to accidentally couple two services), and drift
   detection is a second-order concern that only bites later, incrementally, one missed sync at a
   time — it never blocked the split itself.
5. *(root cause)* Duplication trades a compile-time/import-time guarantee (one shared module, one
   copy of the truth) for a runtime independence guarantee (no service can break another by
   changing shared code) — and nothing has yet replaced the guarantee that was traded away.

**Fixes:**
1. *(immediate)* Keep doing the grep-before-done check by hand — cheap, already the convention, just
   needs actual discipline every time, not just when convenient.
2. *(cheap, mechanical)* Add a CI job that hashes each "supposed to be identical" file
   (`litellm_provider.py`, `subprocess_backend.py`, `agent_runner.py`, etc.) across all packages that
   carry a copy, and fails if they differ without a matching entry in a tracked
   "intentional-divergence" allowlist file.
3. *(process)* When a backlog entry documents a fix to a duplicated file, require it to list every
   package that carries a copy and its sync status explicitly (`§53`/`§55`'s pattern, already used
   inconsistently — make it mandatory).
4. *(tooling)* A `scripts/list_duplicated_files.py` that's generated once from an actual diff of the
   six packages, checked into the repo, so "which files are duplicates" stops being tribal knowledge.
5. *(structural)* Revisit whether *all* duplicated files need to be duplicated, or whether some
   (pure security logic with no per-package variation, e.g. the sanitizer/redaction pattern files)
   could go back to being a single versioned dependency the packages pin to — narrower than a full
   shared `contracts` package, but closing the drift risk for the highest-stakes files without
   re-coupling everything.

### 2. "Verified"/"confirmed green" claims that didn't actually exercise the real path

`§47` claimed CI coverage was "confirmed green" for `model-gateway`; `§49` found this was true only
because `model-gateway` had **zero CI jobs actually running** — there was nothing to be green
*about*. The claim wasn't fabricated, but it was made without checking that the thing being claimed
green was the thing that mattered.

1. Why did "confirmed green" get claimed without the coverage existing? Because a passing CI run was
   observed and taken as confirmation, without checking *which jobs* ran inside it.
2. Why wasn't the job list itself checked? Because "the workflow ran and passed" reads as a complete
   signal if you don't already know a specific job is missing from the matrix.
3. Why didn't the missing job stand out? Because `release-gate.yml`'s job matrices are edited
   piecemeal, service by service, across many separate sessions — a new package can be left out of
   one matrix (`arch-lint`, `domain-coverage`, etc.) while present in others, and nothing diffs the
   matrices against the list of packages that should be in all of them.
4. Why is there no such diff check? Because each `strategy: matrix: service: [...]` list is
   hand-maintained YAML, and the six-package list itself has grown incrementally as packages were
   split out — there's no single source of truth for "these are the six packages, every quality job
   must cover all of them."
5. *(root cause)* "CI passed" and "CI checked the thing I care about" are treated as the same fact
   when they are not — the gap only closes by actually reading which jobs ran, not by reading the
   final `conclusion`.
6. *(the same root cause, one level further)* — separately, `docs/CI_CD_KNOWN_GAPS.md`/`§20.3`
   already documents that `main` has no `required_status_checks` naming `release-gate` at all, so
   even a fully honest, fully-scoped green run doesn't currently block a bad merge — "the gate
   exists and is honest" and "the gate is enforced" are also not the same fact.

**Fixes:**
1. *(immediate)* Before calling anything "verified," read `gh run view <id> --json jobs` and check
   the actual job *names*, not just the aggregate conclusion — this is now the standing rule for
   this session and should stay one.
2. *(cheap, mechanical)* A single YAML anchor or reusable list for "the six backend packages,"
   referenced by every job's `strategy.matrix.service`, so a package can't silently be missing from
   one job's matrix while present in the others.
3. *(process)* When wiring a new package into `release-gate.yml`, check it against every job in the
   file in one pass (as `§57` did for `model-gateway`'s `arch-lint`), not job-by-job across separate
   sessions where earlier gaps are easy to lose track of.
4. *(structural)* Land `docs/CI_CD_KNOWN_GAPS.md`'s already-identified fix — a `required_status_checks`
   rule on `main` naming `release-gate` — so a red (or incomplete) run can't merge regardless of
   whether anyone remembers to check it by hand.
5. *(structural)* Treat "confirmed green" as a claim that always needs its own citation (run ID +
   job list), the same discipline already applied to code fixes — a claim without a run ID is a
   guess, not a verification.

### 3. Escape hatches and shadow-mode flags with no expiry or promotion trigger

Three separate, confirmed instances of the same shape: a control ships `off`/`shadow` "for now," and
then just... stays that way, indefinitely, because nothing ever asks "should this be `enforce` yet?"
`AUTH_ENABLED`/`RBAC_ENABLED`/`AUTHZ_MODE` all default off (`§11.2`); the `organization_id`-empty
tenant fallback was a migration shim with no sunset (`§11.3`); `TOOL_SCOPE_MODE` has been stuck at
`shadow` since `§23.5` pending a product decision that never got made (`§31`); `cosign` signing is a
non-functional stub (`§41.4`).

1. Why do these controls stay in their permissive/off state long after the reason for choosing that
   state has passed? Because nothing tracks *why* the setting is off or *what would need to be true*
   to flip it — the default, once chosen, has no expiry.
2. Why was there no expiry attached when each was introduced? Because each was a reasonable,
   deliberate choice at the time ("don't break dev with no IdP configured," "give legacy tokens a
   grace period," "don't block on an incomplete tool catalog") — the risk of the choice becoming
   permanent by default wasn't the concern being solved for at introduction time.
3. Why doesn't becoming-permanent get caught later? Because there's no periodic audit that asks "is
   this shadow-mode flag still shadow, and if so, why, and is that still a deliberate choice or just
   inertia?" — the working convention (`off|shadow|enforce`, defaulting to `shadow`) governs how
   controls are *introduced*, not how they're *revisited*.
4. Why is there no periodic audit? Because promoting a flag to `enforce` is a product/security
   decision, not a code change, and this project's standing loop is about making code changes — a
   flag stuck pending "product authority over the catalog" (`§31`) has no natural trigger to surface
   it back to whoever can make that call.
5. *(root cause)* "Fail open by default, tighten later" has a clear mechanism for the first half and
   none for the second — the project has good discipline about not defaulting to `enforce` (avoiding
   breaking things), but no symmetric discipline about not defaulting to permissive forever.

**Fixes:**
1. *(immediate)* For any new `off|shadow|enforce` control, write down in the same commit/doc entry
   what observable signal would justify promoting it — even if that signal can't be checked yet.
2. *(cheap, mechanical)* A metric/log line on every fallback/shadow-mode code path that fires
   (`tenant_bind_fallback_used`-style counters, already proposed for `§11.3` specifically) — turns
   "is it safe to flip this" from a guess into a Grafana-observable fact.
3. *(process)* A recurring (not one-off) audit pass — the kind `§45`–`§49` already do for security
   findings — that specifically lists every `shadow`/`off`-by-default control across the codebase
   and asks, for each, "still the right default, or just never revisited?"
4. *(structural)* Attach a tracked owner and an explicit re-review date to any compat shim or
   feature flag at merge time, not just a comment — a shim without a sunset is indistinguishable from
   permanent design six months later.
5. *(structural)* Add the missing startup-time guard already designed for `§11.2` — refuse to start
   with `STAGE=prod` and an insecure default — as the concrete template for the general pattern:
   the fix that actually prevents "permissive forever" is code that makes the permissive state
   impossible in the environment where it matters, not a policy that says someone should check.

### 4. Protocols validated only against their single existing implementation

`AgentRunner` (the dispatcher↔runtime seam Protocol) was typed correctly enough that `AgentRuntime`
— its only implementation — satisfied it, but the registry (`get_agent_runner`) was typed against
the *concrete class*, not the Protocol. Harmless for years, because a class trivially satisfies
itself. The moment a second implementation (`MinimalReactAgentRunner`) was registered and the
registry's return type was correctly widened to the Protocol, `ty check` found that `AgentRunner`
was missing `profile_id` — a parameter the concrete class had silently accepted all along, but the
Protocol never declared (`§56.6`).

1. Why did this gap go unnoticed for so long? Because with exactly one implementation, nothing ever
   forced the Protocol and the concrete class to be checked against each other — the concrete class
   was used directly almost everywhere.
2. Why was the concrete class used directly instead of the Protocol? Because that's the natural,
   lowest-friction path when there's only one implementation — introducing the Protocol type
   everywhere "in case" a second implementation shows up someday is exactly the kind of speculative
   abstraction this project's own conventions discourage.
3. Why didn't type-checking catch the drift earlier? Because `ty check src` only checks what's
   actually annotated as the Protocol type — a registry typed as `dict[str, Callable[[], AgentRuntime]]`
   gives the type checker no reason to ever compare `AgentRuntime` against `AgentRunner`'s Protocol
   surface.
4. Why is this specifically risky for *this* project's stated goal ("switch core to any agent on the
   market")? Because the entire point of the split is that a second, third, Nth `AgentRunner`
   implementation is expected to arrive — this is exactly the seam where a single-implementation
   Protocol/class drift is most likely to recur, not an edge case.
5. *(root cause)* A Protocol with one implementation is untested as a Protocol — it's just
   documentation until a second, independent implementation forces the type checker to actually
   verify the contract both sides agree on.

**Fixes:**
1. *(immediate, already applied)* Fixed the concrete gap: `AgentRunner.arun` now declares
   `profile_id`, matching what `AgentRuntime` already accepted and `PlannerRuntime` already required.
2. *(cheap, mechanical)* Type the registry (`_AGENT_RUNNERS`, `get_agent_runner`,
   `configure_agent_runner`) against the Protocol, not the concrete class, permanently — done this
   session, keep it that way even if `react` were ever removed.
3. *(process)* Whenever a second implementation of any single-implementation Protocol in this
   codebase is added (agent runner, execution backend, tool registry, etc.), treat the type-checker
   diagnostics that appear as signal, not noise — they're surfacing exactly the kind of latent drift
   this pattern predicts.
4. *(structural)* Actively look for other single-implementation Protocols in `cys_core.application.ports`
   that are the intended swap points for "switch core to any agent" — `ExecutionBackend`,
   `ModelConnector`, `ToolRegistry`'s port — and sanity-check each one's Protocol against its one
   real implementation now, rather than waiting for a second implementation to force the issue.
5. *(structural)* For any future seam that's explicitly designed to be swappable (which, per the
   project's stated goal, most of the agent-runtime boundary is), consider writing a minimal fake
   second implementation early — even a throwaway one — purely to force the Protocol/concrete-class
   contract to be checked, before a real second implementation shows up under time pressure.

### 5. Local static checks pass while CI's actual invocation shape fails

Two distinct incidents, same shape: something looked verified locally, but the specific way CI
invokes the check wasn't reproduced, so a real bug shipped anyway. `model-gateway`'s new
`tests/architecture/` couldn't import `scripts.verify_import_boundaries` in CI
(`ModuleNotFoundError`) even though `ruff`, `ty check`, `lint-imports`, and running the scripts
*directly* all passed locally — the scripts were never actually *collected* as pytest modules
locally before pushing (`§57.1`/`§57.2`). Separately, the `subprocess_backend.py` "defense in depth"
change passed `ruff`/`ty check`/`lint-imports` locally and broke a real regression test in CI, because
the standing rule against running `pytest` locally meant that specific test was never re-run before
pushing (`§56.2`).

1. Why did both bugs reach CI instead of being caught locally? Because the local verification suite
   for this project is deliberately restricted to non-test static checks (`ruff`/`ty check`/
   `lint-imports`/`docker build`/etc.) — real test execution and pytest collection are CI-only by
   standing rule.
2. Why is that restriction in place? Because running the full test suite locally is slow, and the
   project's standing instruction is to dispatch CI and keep moving rather than block a session on
   local test runs — a deliberate, reasonable trade for velocity.
3. Why didn't a collection-only check (`pytest --collect-only`, which imports every test module
   without running any test body) close this gap, given it's not "running the suite"? Because it
   wasn't part of the established local-check list — the list was built around *linting* categories
   (style, types, imports), not around *"does the test file even import cleanly."*
4. Why is import-time collection failure a distinct risk from the things the existing local checks
   cover? Because `ruff`/`ty check` verify a file in isolation against its own syntax/types; they
   don't verify that `pytest`'s actual module-resolution mechanism (`sys.path`, `pythonpath` ini
   config, conftest side effects) can find and import it the way CI will.
5. *(root cause)* The local-check list optimizes for "fast feedback on code quality" and correctly
   excludes "run the tests," but a static-analysis-only list has a blind spot for anything whose
   correctness depends on *runtime import machinery* rather than *code shape* — collection is
   import-time, not test-execution-time, and was never separated out as its own category.

**Fixes:**
1. *(immediate, already applied)* `uv run pytest <dir> --collect-only -q` was used this session to
   both reproduce and confirm the fix for the `model-gateway` import bug — it imports every test
   module without executing a single test body, so it doesn't cross the "never run test suites
   locally" line while still catching this exact class of bug.
2. *(cheap, mechanical)* Add `pytest --collect-only` (not a full run) to the standing list of
   locally-acceptable static checks, explicitly, alongside `ruff`/`ty check`/`lint-imports` — it's
   categorically a linting/import-resolution check, not a test-suite run.
3. *(process)* When porting a file (config, script, test) from one of the duplicated packages to
   another (as `§57` ported `tool-gateway`'s pattern to `model-gateway`), don't assume an identical
   file behaves identically in a different package — the two packages' `tests/conftest.py` presence
   was the entire difference here, and it wasn't visible from reading either file alone.
4. *(structural)* Whenever a new package's `pyproject.toml` pytest config is written by copying
   another package's, diff *why* each setting exists (e.g., `pythonpath = ["src", "../.."]`'s two
   entries), not just copy the values — this bug existed because `model-gateway` copied the ini
   settings but not the `tests/conftest.py` side effect the other packages silently depend on.
5. *(structural)* For the `subprocess_backend.py` class of bug specifically (a "plausible-sounding"
   change to shared low-level infra) — before changing parsing/IPC-contract code that has an
   existing regression test guarding a specific behavior, read that test and the discovery doc it
   references (`docs/MICROSERVICES_SPLIT_PHASES_DETAIL.md`'s Discovery H.1) *first*, to check
   whether the existing behavior was already a deliberate decision, before treating a new theory as
   "defense in depth."
