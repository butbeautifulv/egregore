# egregore-worker

Consumes `WorkerJob` messages from the queue and runs the agent-execution
runtime (LangChain/LangGraph today). Fully self-contained — its own
physical copy of domain models, port interfaces, and generic infra clients
(no shared package with `egregore-api`, see `docs/MICROSERVICES_SPLIT_PLAN.md`
§18). See the task #38 plan for why the packages are independent: the queue
message and Postgres rows are the only things allowed to cross the
api/worker boundary, so a future swap of the agent runtime (or a future
rewrite of the api service in another language) never needs to touch this
package's counterpart.
