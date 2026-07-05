# Smoke test outlines (Stream D0)

## Interactive — run → tool → schema (p0-09)

```gherkin
Given API with AUTH_ENABLED=false and in-memory catalog
When POST /runs with persona=consultant and user message
Then response status 200
And at least one tool_call TraceEvent or tool invocation metric
And output validates against agent output_schema when set
```

**pytest hook:** `tests/integration/` (future) — patch `AgentRuntime.arun` to return schema-valid JSON.

## Worker — ingress → worker → bus → memory (p0-10)

> Blocked on que-08 lag gate for prod; outline valid for dev/test.

```gherkin
Given POST /events manual.investigation
When planner completes and worker consumes job
Then job_store marks completed
And bus publishes finding to critic channel
And investigation memory records persona completion
```

**pytest hook:** extend `tests/worker/test_investigation_lifecycle.py` with bus + memory assertions.
