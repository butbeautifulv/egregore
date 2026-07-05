# Datasources RBAC and governance

## Default posture

- **GET-only** for datasource capabilities unless explicitly granted mutate.
- Authz subject: **persona** from job payload + profile/tenant from run context.
- Attach-time filtering removes unauthorized tools; exec-time re-checks at gateway.

## Staging lifecycle

| Status | Meaning |
|--------|---------|
| `draft` | Experimental connector; read-only by default |
| `vetted` | Reviewed for production read paths |
| `builtin` | Platform-shipped; promotion requires admin |

## Write gate

Mutations require `WriteGateRequest`: `actor`, `reason`, and `diff_summary`.
Missing fields → deterministic deny with audit trace event.

## Promotion

See `PromotionRule` in `cys_core/domain/datasources/governance.py`.
Only privileged personas may grant mutate capability or enable writes.

## Runbook (local)

1. Seed catalog: `POST /catalog/seed`
2. List datasources via catalog port (in-memory adapter in tests)
3. Invoke tool through gateway — verify `AuthorizationDecision` in trace
4. Langfuse: filter observations by `datasource_id` metadata

## Eval / verifier (E2)

- Outcome scoring: `eval_outcome.py` (τ-bench-like assertions)
- Optional 2-pass verifier wired into trace critic when enabled
- Partial action similarity is **diagnostic only** — does not gate pass/fail by default
