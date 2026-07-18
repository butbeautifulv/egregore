# egregore-model-gateway

The Model Gateway — the network chokepoint for LLM calls, symmetrical to the Tool Gateway
(`backend/tool-gateway`). See `docs/MICROSERVICES_SPLIT_PLAN.md` §22.9 for the design rationale
and §29 for this implementation's notes.

Any agent runtime, regardless of framework, is configured to send model calls here instead of
calling litellm/the provider API directly. This service enforces — independent of whether the
calling runtime cooperates —:

- **Immutable-rules / system-prompt-digest validation**: rejects a call whose system prompt is
  missing `GLOBAL_RULES:`/`SECURITY_RULES:` markers, or whose digest doesn't match an expected one
  supplied by the caller.
- **Input sanitization**: classifies and sanitizes every `user`/`tool`-role message for prompt
  injection before it reaches the model (same `InputSanitizer` logic used in-process by worker's
  `PromptContextMiddleware`, framework-neutral).
- **Output-leakage guardrails**: scans the model's response for system-prompt leakage before
  returning it to the caller.

A refused call still returns HTTP 200 with `refused: true` and a `refusal_reason` — the caller
(the agent runtime) decides what to do with a refusal; this service's job is only to enforce, not
to shape agent behavior.

## Run

```
uv run egregore-model-gateway
```

Config via env vars (see `src/bootstrap/settings.py`): `MODEL_GATEWAY_HOST`, `MODEL_GATEWAY_PORT`,
`MODEL_GATEWAY_DEFAULT_MODEL`, `MODEL_GATEWAY_AUTH_ENABLED` + `MODEL_GATEWAY_SHARED_SECRET`. Model
provider credentials (`OPENAI_API_KEY` etc.) are resolved by litellm itself from its own env vars,
not duplicated into this service's settings.

## Test

```
./scripts/pytest_batches.sh
```
