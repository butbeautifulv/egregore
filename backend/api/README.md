# egregore-api

FastAPI CRUD + event ingress. Depends on `egregore-contracts` for domain
models, port interfaces, and generic infra clients — never on
`egregore-worker`. See `docs/MICROSERVICES_SPLIT_PLAN.md` and the task #38
plan for why: the queue message and Postgres rows are the only things
allowed to cross the api/worker boundary.

One accepted exception (plan §1.2): the meta-LLM engagement planner's
background task (`interfaces/api/planner_tasks.py`) calls into
`MetaPlanner`/`PlanInvestigation` with `runtime=None` here — the real agent
runtime lives in `egregore-worker` and duplicating it into this package was
rejected as worse than the alternative. This means meta-LLM async planning
(gated behind `ENGAGEMENT_ASYNC_PLANNING`, default `true`) does not actually
work from this build until a follow-up moves it to be genuinely
worker-side (API enqueues a planning job instead of running it in-process).
