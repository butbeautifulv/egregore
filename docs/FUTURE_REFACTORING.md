# Future Refactoring — imagination, not a plan

> **This is not a to-do list.** [`MICROSERVICES_SPLIT_PLAN.md`](MICROSERVICES_SPLIT_PLAN.md) is the
> committed, prioritized work. This file is speculative: what egregore's architecture could become
> if the aspirational/deferred items already scattered across [`MSP_BACKLOG.md`](MSP_BACKLOG.md) and
> the plan's §2 were actually carried to their end state, plus a KISS/DRY-focused problem-solution
> entry extending [`MSP_START_HERE.md`](MSP_START_HERE.md)'s reflection. Nothing here is scoped,
> estimated, or approved — it needs product/architecture buy-in before any of it becomes a real
> backlog item.

## The shape of a fully-realized egregore

Five things this codebase already gestures at, half-built, scattered across the backlog — imagined
here as if each were carried all the way through.

### 1. A domain-agnostic core with SOC as one installable pack

Today the "core" hardcodes SOC six times over (`EventType`/`WorkerAgentName` closed `Literal`s, 11
concrete `Finding` subclasses, `ESCALATION_ONLY_PATHS`/`READ_ONLY_TOOLS`, unconditional SIEM/Veil/
Nessus tool registration, `DEFAULT_PROFILE_ID`) — a target model already exists (`§8`, `§24.1`) but
the refactor is large and cross-cutting. Imagine it finished: `cys_core.domain` knows nothing about
SOC specifically. Event types, finding shapes, tool catalogs, and escalation policy all become data
— a "domain pack" a deployment installs, the same way `AgentRunner` is already a swappable
implementation rather than a hardcoded class. A second domain pack (say, a fraud-investigation
pack, or a generic ops-incident pack) becomes a config change, not a fork. This is the same shape as
the user's own stated goal for the agent core ("switch core to any agent on the market, inside a
safe system") applied one layer up — the *domain*, not just the *agent implementation*, becomes
swappable.

### 2. One memory tier, not three parallel ones

`domain/memory`'s episodic store, the `memory_type` schema's dormant `lesson`/`preference` slots
(`§9`), and `InMemoryReflexionStore`'s process-local self-critique loop (`§9.2.4`) are three
adjacent, never-unified concepts for "state that should outlive one call." Imagine them merged: a
single `MemoryWriteService` that every stateful subsystem calls into, tiered by TTL and scope
(session-local scratch vs. cross-session lesson vs. long-term preference), all backed by the same
durable store, all subject to the same tenant-scoping and retention policy. Reflexion stops being a
parallel in-memory list and becomes a caller of the same service the episodic memory already uses.

### 3. A real agent marketplace behind `AgentRunner`

`"langgraph"` and `"react"` are registered today (`§52.3`, `§56.6`) — proof the seam works, not the
end state. Imagine three or four more: a pure-function/no-tools runner for cheap classification
jobs, a wrapper around a third-party hosted agent API, a deliberately adversarial/red-team runner
for testing the dispatcher's own defenses. Each just implements `AgentRunner`'s Protocol and gets
registered — `dispatcher`, `tool-gateway`, `model-gateway`, and every security control in between
never change. This is the concrete, load-bearing test of "switch core to any agent on the market,
inside a safe system": the day a wrapper around an arbitrary external agent SDK can be dropped in
and still have every sanitizer/guardrail/budget-tracker/scope-check apply to it unmodified, the
sentence is proven, not just architected for.

### 4. Every deploy mode actually deployable, sandboxed properly

`subprocess`/same-host is proven (`§56`); `docker`/`k8s` `ExecutionBackend` modes are still
undecided (plan §1 item 1); gVisor/Kata sandbox isolation is documentation only (`§22.5`). Imagine
the full ladder built out: same-host subprocess for local dev, Docker-per-job for single-host
multi-tenant isolation, full K8s Jobs for horizontal scale, gVisor/Kata for the untrusted-code case —
each an `ExecutionBackend` implementation behind the same interface, selected by config, not by
which code path happened to get written first.

### 5. Supply chain and authz gates that are real, not stubs

`cosign` signing is a non-functional stub (`§41.4`); `main` has no `required_status_checks` naming
`release-gate` (`§20.3`); `TOOL_SCOPE_MODE` is stuck at `shadow` (`§23.5`, `§31`); ReBAC doesn't scope
the agent-executor side (`§11.4`). None of these are hard problems individually — they're each a
finished design waiting on a decision or a few days of wiring. Imagine all four flipped: every image
actually signed and verified before deploy, every merge to `main` actually blocked on a red gate,
every tool call actually checked against the catalog instead of just logged in shadow mode, every
persona's tool access actually scoped by OpenFGA instead of one flat gateway role. The "safe system"
half of the user's goal is mostly these four switches, not new architecture.

---

## Problem → Solution, 6th entry: Simplification & KISS/DRY

Extends [`MSP_START_HERE.md`](MSP_START_HERE.md)'s five-problem reflection with one more, specific
to the complexity this imagined future state would have to actually simplify rather than add to.

### 6. Complexity accumulates because duplication and special-casing are always the locally-cheapest choice

The "duplicate everything" convention (`§18`) is a deliberate, reasoned decision — but it's also
exactly the kind of decision that's individually correct and collectively expensive: six physical
copies of `cys_core.domain`/`bootstrap`, six hardcoded references to the SOC domain scattered through
core instead of one config-driven pack, three parallel "remember things across calls" subsystems
(episodic memory, Reflexion, `memory_type`'s unused slots) instead of one. None of these were
mistakes at the time they were introduced — each solved its immediate problem with the least
disruption to everything around it.

1. Why does the codebase have six copies of the same domain/bootstrap code, six hardcoded SOC
   references, and three parallel memory subsystems, instead of one of each? Because each was added
   to solve one immediate, local problem (process independence for the split; SOC being the only
   customer when the core was built; a lightweight self-critique loop that didn't need to be a full
   memory tier yet), and generalizing at the time would have meant solving a problem nobody had yet.
2. Why is solving-only-the-immediate-problem the default? Because it's cheaper and lower-risk in the
   moment — a physical copy that definitely doesn't couple two services is safer *right now* than a
   shared abstraction whose boundary might be wrong; a hardcoded `Literal` shipped faster than a
   config-driven pack when there was exactly one domain to support.
3. Why doesn't the cost of that default get revisited once the second/third instance shows up
   (second package needing the same fix, second domain concept, second memory-shaped subsystem)?
   Because there's no standing checkpoint that asks "is this still one-off, or is this now a
   pattern?" — the individual decisions are each reasonable in isolation, and nothing aggregates
   them into a single "we now have six of these" signal until someone happens to notice.
4. Why doesn't anyone happen to notice sooner? Because the people making each individual decision
   are (correctly) focused on the concrete task in front of them — noticing "this is the third
   parallel memory-shaped thing" requires stepping back across the whole system, which is exactly
   the kind of cross-cutting view a single-task session doesn't naturally have.
5. *(root cause)* KISS and DRY are both *locally* satisfied by every individual decision here (each
   one really is the simplest fix for its own moment) while being *globally* violated by their sum —
   there's no mechanism that aggregates many locally-simple choices into a visible signal that the
   system as a whole has stopped being simple.

**Fixes:**
1. *(immediate)* When a fix or feature is about to become the *second* instance of a pattern (second
   duplicated file needing the same change, second hardcoded domain-specific `Literal`, second
   "remember state across calls" subsystem), name that explicitly in the commit/backlog entry — the
   trigger for "this might be a pattern now" is the second occurrence, not the fifth.
2. *(cheap, mechanical)* A recurring audit question, added to the same standing-audit cadence
   `§45`–`§49` already use for security findings: "what exists in 3+ near-identical copies today
   that didn't a year ago?" — turns accumulating duplication into something looked for, not
   something stumbled on.
3. *(process)* Before adding a new special case or a new parallel subsystem, check whether it's
   actually a new instance of something already in the codebase under a different name (Reflexion
   vs. episodic memory was exactly this) — a five-minute grep against `domain/memory`'s existing
   shape would have surfaced the overlap before Reflexion was built as its own thing.
4. *(structural)* Apply the target models that already exist on paper (`§8`'s domain-genericization
   model, `§9.3`'s unified memory tier) opportunistically — the next time either area needs *any*
   change for an unrelated reason, do the generalization then, rather than waiting for a dedicated
   "big refactor" session that competes with every other priority and keeps losing.
5. *(structural, the actual KISS/DRY discipline)* Treat "how many places would this change need to
   happen" as a first-class question at design time, not an afterthought at review time — the
   physical-package-duplication trade-off (`§18`) was made explicitly and is worth keeping as-is
   (real independence guarantee), but *every other* duplication in this codebase (domain hardcoding,
   parallel memory subsystems, ad-hoc id-generation call sites — `§48.4`/`§50.1`) was never an
   equally deliberate trade — it just accreted. The distinction worth institutionalizing: duplication
   is fine when it's a named, reviewed trade for a real guarantee (independence, security isolation);
   it's a liability when it's just "this was the fastest way to ship the immediate task."
