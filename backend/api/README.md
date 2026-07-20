# egregore-api

FastAPI CRUD + event ingress. Fully self-contained — its own physical copy
of domain models, port interfaces, and generic infra clients (no shared
package with `egregore-worker`, see `docs/MSP_BACKLOG.md`
§18). See the task #38 plan for why the packages are independent: the
queue message and Postgres rows are the only things allowed to cross the
api/worker boundary.

No exceptions: meta-LLM engagement planning needs the real agent runtime
(`catalog_planner_strategy.py`'s `self.runtime.arun(...)`), so this package
never constructs a `MetaPlanner`/`PlanInvestigation` at all. For
`PlanStrategy.META_LLM`, `StartEngagement.execute()` enqueues a
`WorkerJob(persona="planner", work_kind="engagement_plan")` and returns —
worker's `RunWorkerJob` recognizes that job (`is_engagement_plan_job`) and
runs `EngagementPlannerRunner`, the real planner with the real runtime,
which enqueues the resulting persona jobs itself. See
`docs/MSP_BACKLOG.md` §16.
