# egregore-contracts

Shared domain models, port interfaces, and generic infrastructure adapters
(Postgres/Kafka/Redis clients, catalog/job/engagement persistence, policy
and authz port adapters) used by both the `api` and `worker` services.

This is the only thing allowed to cross the api/worker boundary in source
form — everything else crosses only as the queue message (`WorkerJob` JSON)
or Postgres rows. See `docs/MICROSERVICES_SPLIT_PLAN.md` and the task #38
plan for the reasoning.

No FastAPI, no agent-execution frameworks (`langchain`/`langgraph`/
`deepagents`) — those stay `worker`-only, which is the entire point of the
split (see `bootstrap/settings.py`'s neighbors for the exception:
`langchain-core` is a base-classes/schema dependency of two port
definitions, not the execution engine).
