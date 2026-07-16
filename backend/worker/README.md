# egregore-worker

Consumes `WorkerJob` messages from the queue and runs the agent-execution
runtime (LangChain/LangGraph today). Depends on `egregore-contracts` for
domain models, port interfaces, and generic infra clients — never on
`egregore-api`. See `docs/MICROSERVICES_SPLIT_PLAN.md` and the task #38
plan for why: the queue message and Postgres rows are the only things
allowed to cross the api/worker boundary, so a future swap of the agent
runtime (or a future rewrite of the api service in another language) never
needs to touch this package's counterpart.
