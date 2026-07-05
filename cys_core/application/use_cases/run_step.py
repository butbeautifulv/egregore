from __future__ import annotations

import json
from typing import Any, Protocol

from cys_core.application.plans_as_hints import load_plan_hints
from cys_core.application.ports.catalog import AgentCatalogPort
from cys_core.application.ports.observability.judge_backend import JudgeBackendPort
from cys_core.application.ports.context_summarizer import ContextSummarizerPort
from cys_core.application.ports.profile_policy import ProfilePolicyPort
from cys_core.application.ports.reflexion import ReflexionLesson, ReflexionStorePort
from cys_core.application.ports.run_state import RunStateStorePort
from cys_core.application.ports.work_todo import WorkTodoStorePort
from cys_core.application.runs.attachment_hints import process_attachment_hints
from cys_core.application.runs.plan_helpers import format_todo_snapshot
from cys_core.application.runs.plan_strict import has_failed_todos, merge_plan_delta_with_policy
from cys_core.application.runs.run_budget import run_session_budget
from cys_core.application.skills.catalog import list_skill_metadata
from cys_core.application.spawn_broker import SubagentSpawnBroker
from cys_core.application.use_cases.analyze_task_hints import AnalyzeTaskHints
from cys_core.application.ports.tracing_ports import ApplicationTracingPort, NOOP_APPLICATION_TRACING
from cys_core.application.use_cases.evaluate_trace_critic import EvaluateTraceCritic
from cys_core.application.use_cases.extract_structured_output import enrich_conductor_result
from cys_core.application.policy_resolver import get_profile_policy_resolver
from cys_core.application.runtime_config import (
    get_egregore_strict_plan,
    get_task_hints_enabled,
    get_trace_critic_enabled,
    get_trace_critic_hitl_on_exhausted,
    get_use_run_kernel,
)
from cys_core.application.runs.agent_run_kernel import AgentRunKernel
from cys_core.application.runs.kernel_mappers import run_state_to_kernel_request
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.domain.runs.checkpoint import checkpoint_key
from cys_core.domain.runs.models import InteractionMode, RunContext
from cys_core.domain.runs.plan_models import WorkPlan, WorkTodo
from cys_core.domain.runs.state_models import RunState, RunStatus


def _default_task_hints() -> AnalyzeTaskHints:
    try:
        from cys_core.application.runtime_config import get_reasoning_llm_settings

        if not str(get_reasoning_llm_settings().get("model", "")).strip():
            return AnalyzeTaskHints()
        from cys_core.llm.reasoning import get_reasoning_model_connector

        return AnalyzeTaskHints(model=get_reasoning_model_connector().create_model())
    except Exception:
        return AnalyzeTaskHints()


class RunRuntime(Protocol):
    async def arun(
        self,
        name: str,
        user_input: str,
        *,
        session_id: str | None = None,
        tenant_id: str = "default",
        investigation_id: str = "",
        profile_id: str = DEFAULT_PROFILE_ID,
    ) -> dict[str, Any]: ...


def _parse_work_plan(result: dict[str, Any]) -> WorkPlan | None:
    if "plan" in result and isinstance(result["plan"], dict):
        try:
            return WorkPlan.model_validate(result["plan"])
        except Exception:
            return None
    for key in ("work_plan", "WorkPlan"):
        if key in result and isinstance(result[key], dict):
            try:
                return WorkPlan.model_validate(result[key])
            except Exception:
                return None
    plan_delta = result.get("plan_delta")
    if isinstance(plan_delta, dict) and plan_delta:
        try:
            return WorkPlan.model_validate(plan_delta)
        except Exception:
            return None
    return None


from cys_core.domain.runs.status_policy import derive_run_status


def _merge_todos_from_result(
    result: dict[str, Any],
    *,
    todos: list[WorkTodo],
) -> list[WorkTodo]:
    merged = list(todos)
    if result.get("todos"):
        merged = [WorkTodo.model_validate(item) for item in result["todos"]]
    plan_delta = result.get("plan_delta")
    if isinstance(plan_delta, dict):
        merged = merge_plan_delta_with_policy(merged, plan_delta)
    return merged


def _attachment_paths(state: RunState) -> list[str]:
    paths: list[str] = []
    for item in state.attachments:
        if isinstance(item, dict) and item.get("path"):
            paths.append(str(item["path"]))
        elif isinstance(item, str):
            paths.append(item)
    return paths


def _inject_reflexion_hints(state: RunState, ctx: RunContext, reflexion_store: ReflexionStorePort) -> None:
    inv_id = ctx.context_id
    lessons = reflexion_store.list_for_investigation(ctx.tenant_id, inv_id)
    for lesson in lessons:
        note = f"reflexion: {lesson}"
        if note not in state.reasoning_notes:
            state.reasoning_notes.append(note)


def _build_step_prompt(
    *,
    state: RunState,
    user_input: str,
    ctx: RunContext,
    todos: list[WorkTodo],
) -> str:
    payload: dict[str, Any] = {
        "goal": state.goal or user_input,
        "mode": (ctx.mode or InteractionMode.AGENT).value,
        "input": user_input,
        "run_context": ctx.model_dump(),
        "routing_hints": load_plan_hints(),
        "skill_catalog": list_skill_metadata(ctx.profile_id),
        "todo_snapshot": format_todo_snapshot(todos),
        "todos": [t.model_dump() for t in todos],
        "strict_plan": get_egregore_strict_plan(),
    }
    if state.reasoning_notes:
        payload["task_hints"] = state.reasoning_notes
    if state.context_summary:
        payload["context_summary"] = state.context_summary
    attach_paths = _attachment_paths(state)
    if attach_paths:
        payload["attachments"] = state.attachments
        payload["attachment_hints"] = process_attachment_hints(attach_paths)
    if state.last_trace_verdict:
        payload["last_trace_verdict"] = state.last_trace_verdict
    if state.trace_rerun_count:
        payload["trace_rerun_count"] = state.trace_rerun_count
    return json.dumps(payload, ensure_ascii=False)


def _maybe_failed_summary(
    state: RunState,
    user_input: str,
    *,
    context_summarizer: ContextSummarizerPort,
) -> None:
    failed = state.last_trace_verdict.get("verdict") == "fail" or has_failed_todos(state.todos)
    if not failed:
        return
    blob = json.dumps(state.last_result, ensure_ascii=False, default=str)
    state.context_summary = context_summarizer.summarize(
        goal=state.goal or user_input,
        messages_text=blob,
        prior_summary=state.context_summary,
    )


class RunStep:
    """Execute one step for a RunContext (stateless or stateful)."""

    def __init__(
        self,
        *,
        runtime: RunRuntime,
        state_store: RunStateStorePort,
        catalog: AgentCatalogPort,
        todo_store: WorkTodoStorePort,
        context_summarizer: ContextSummarizerPort,
        reflexion_store: ReflexionStorePort,
        policy_port: ProfilePolicyPort,
        judge_backend: JudgeBackendPort | None = None,
        task_hints: AnalyzeTaskHints | None = None,
        application_tracing: ApplicationTracingPort | None = None,
    ) -> None:
        self.runtime = runtime
        self.state_store = state_store
        self.catalog = catalog
        self.todo_store = todo_store
        self.context_summarizer = context_summarizer
        self.reflexion_store = reflexion_store
        self.policy_port = policy_port
        self.spawn_broker = SubagentSpawnBroker(self.catalog, policy_port=policy_port)
        self._task_hints = task_hints or _default_task_hints()
        self._judge_backend = judge_backend
        self._tracing = application_tracing or NOOP_APPLICATION_TRACING

    def _policy_resolver(self):
        return get_profile_policy_resolver()

    def _trace_critic_for(self, profile_id: str) -> EvaluateTraceCritic:
        threshold = self._policy_resolver().trace_critic_threshold(profile_id)
        return EvaluateTraceCritic(
            judge_backend=self._judge_backend,
            threshold=threshold,
            application_tracing=self._tracing,
        )

    def _trace_policy(self, profile_id: str):
        return self._policy_resolver().policy(profile_id).trace_critic

    async def _run_conductor(
        self,
        *,
        persona: str,
        prompt: str,
        session_id: str,
        ctx: RunContext,
        state: RunState,
        todos: list[WorkTodo],
        mode: InteractionMode,
    ) -> tuple[dict[str, Any], list[WorkTodo]]:
        if get_use_run_kernel() and persona == "conductor":
            kernel = AgentRunKernel(self.runtime)
            request = run_state_to_kernel_request(
                state=state,
                ctx=ctx,
                user_input=prompt,
                persona=persona,
                prompt=prompt,
            )
            kernel_result = await kernel.execute(request)
            result = kernel_result.output
            if isinstance(result, dict) and kernel_result.trajectory.events:
                result = {**result, "_kernel_trajectory": kernel_result.trajectory.model_dump(mode="json")}
        else:
            with run_session_budget(session_id, persona):
                result = await self.runtime.arun(
                    persona,
                    prompt,
                    session_id=session_id,
                    tenant_id=ctx.tenant_id,
                    investigation_id=ctx.context_id,
                    profile_id=ctx.profile_id,
                )
        last_result = result if isinstance(result, dict) else {"raw": result}
        if isinstance(last_result, dict):
            todos = _merge_todos_from_result(last_result, todos=todos)
            self.todo_store.replace_todos(ctx.tenant_id, ctx.context_id, todos)
            state.todos = todos
            last_result = enrich_conductor_result(last_result, goal=state.goal or prompt)
            from cys_core.application.reasoning.conductor_sgr import (
                filter_spawn_requests_by_sgr,
                persist_sgr_fields_to_state,
            )

            if isinstance(last_result, dict):
                last_result["spawn_requests"] = filter_spawn_requests_by_sgr(last_result)
                persist_sgr_fields_to_state(state, last_result)
        state.step_count += 1

        skip_trace_critic = isinstance(last_result, dict) and last_result.get("enough_data") is True
        if (
            not skip_trace_critic
            and get_trace_critic_enabled()
            and persona in ("conductor", "gaia_solver")
            and state.step_count
            % max(1, self._trace_policy(ctx.profile_id).every_n_steps or self._policy_resolver().trace_critic_every_n(ctx.profile_id))
            == 0
        ):
            verdict = self._trace_critic_for(ctx.profile_id).execute(
                goal=state.goal or prompt,
                trace=last_result,
                step_count=state.step_count,
                engagement_id=ctx.context_id,
            )
            state.last_trace_verdict = verdict.model_dump()
            try:
                from cys_core.application.persona_quality_hooks import record_trace_critic

                record_trace_critic(persona, passed=verdict.verdict != "fail", profile_id=ctx.profile_id)
            except Exception:
                pass
            if verdict.verdict == "fail":
                lesson = verdict.reasoning or "; ".join(verdict.issues) or "trace critic failed"
                self.reflexion_store.append(
                    ReflexionLesson(
                        investigation_id=ctx.context_id,
                        tenant_id=ctx.tenant_id,
                        lesson=lesson,
                        source="trace_critic",
                    )
                )
            if verdict.should_rerun and isinstance(last_result, dict):
                last_result["trace_critic"] = verdict.model_dump()
                if state.trace_rerun_count < (
                    self._trace_policy(ctx.profile_id).rerun_max
                    or self._policy_resolver().trace_critic_rerun_max(ctx.profile_id)
                ):
                    state.trace_rerun_count += 1
                    improvement = verdict.reasoning or "; ".join(verdict.issues) or "Improve action trace."
                    state.reasoning_notes = [*state.reasoning_notes, f"trace_critic: {improvement}"]
                    rerun_prompt = _build_step_prompt(
                        state=state,
                        user_input=f"Rerun requested by trace critic. Address: {improvement}",
                        ctx=ctx,
                        todos=todos,
                    )
                    return await self._run_conductor(
                        persona=persona,
                        prompt=rerun_prompt,
                        session_id=session_id,
                        ctx=ctx,
                        state=state,
                        todos=todos,
                        mode=mode,
                    )
                if (self._trace_policy(ctx.profile_id).hitl_on_exhausted or get_trace_critic_hitl_on_exhausted()) and isinstance(
                    last_result, dict
                ):
                    last_result["trace_critic_escalation"] = True
                    last_result["status"] = "awaiting_user"
                    try:
                        from cys_core.application.persona_quality_hooks import record_hitl_pause

                        record_hitl_pause(persona, profile_id=ctx.profile_id)
                    except Exception:
                        pass
        return last_result, todos

    async def execute(
        self,
        ctx: RunContext,
        user_input: str,
        *,
        persona: str = "conductor",
    ) -> dict[str, Any]:
        with self._tracing.span(
            "run.step",
            engagement_id=ctx.context_id,
            tenant_id=ctx.tenant_id,
            persona=persona,
        ):
            return await self._execute_step(ctx, user_input, persona=persona)

    async def _execute_step(
        self,
        ctx: RunContext,
        user_input: str,
        *,
        persona: str = "conductor",
    ) -> dict[str, Any]:
        state = self.state_store.get(ctx.tenant_id, ctx.context_id, ctx.kind.value)
        if state is None:
            state = RunState(run_context=ctx, goal=user_input, mode=ctx.mode, status=RunStatus.IN_PROGRESS)
        mode = ctx.mode or InteractionMode.AGENT
        session_id = checkpoint_key(ctx, persona=persona)
        todos = self.todo_store.list_todos(ctx.tenant_id, ctx.context_id) or state.todos

        _inject_reflexion_hints(state, ctx, self.reflexion_store)

        if (
            persona in ("conductor", "gaia_solver")
            and mode == InteractionMode.AGENT
            and get_task_hints_enabled()
            and not state.reasoning_notes
            and state.step_count == 0
        ):
            state.reasoning_notes = self._task_hints.execute(state.goal or user_input)

        if state.step_count >= 3 and state.last_result:
            trace_blob = json.dumps(state.last_result, ensure_ascii=False, default=str)
            if len(trace_blob) > 2500:
                state.context_summary = self.context_summarizer.summarize(
                    goal=state.goal or user_input,
                    messages_text=trace_blob,
                    prior_summary=state.context_summary,
                )

        prompt = _build_step_prompt(state=state, user_input=user_input, ctx=ctx, todos=todos)

        if mode == InteractionMode.PLAN:
            with run_session_budget(session_id, persona):
                result = await self.runtime.arun(
                    persona,
                    prompt,
                    session_id=session_id,
                    tenant_id=ctx.tenant_id,
                    investigation_id=ctx.context_id,
                    profile_id=ctx.profile_id,
                )
            plan = _parse_work_plan(result if isinstance(result, dict) else {})
            if plan is None:
                raw = result if isinstance(result, dict) else {}
                plan = WorkPlan(rationale=str(raw.get("rationale", "plan generated")), awaiting_user_input=False)
            state.plan = plan
            if plan.todos:
                self.todo_store.replace_todos(ctx.tenant_id, ctx.context_id, plan.todos)
                state.todos = plan.todos
            state.last_result = {"plan": plan.model_dump()}
            state.status = RunStatus.AWAITING_PLAN_APPROVAL
        elif ctx.is_stateful() or persona in ("conductor", "gaia_solver"):
            last_result, todos = await self._run_conductor(
                persona=persona,
                prompt=prompt,
                session_id=session_id,
                ctx=ctx,
                state=state,
                todos=todos,
                mode=mode,
            )
            state.last_result = last_result
            state.status = derive_run_status(state.last_result, mode=mode)
            _maybe_failed_summary(state, user_input, context_summarizer=self.context_summarizer)
        else:
            ephemeral_session = f"worker:{persona}:{ctx.context_id}"
            with run_session_budget(ephemeral_session, persona):
                result = await self.runtime.arun(
                    persona,
                    prompt,
                    session_id=ephemeral_session,
                    tenant_id=ctx.tenant_id,
                    investigation_id=ctx.context_id,
                    profile_id=ctx.profile_id,
                )
            state.last_result = result if isinstance(result, dict) else {"raw": result}
            state.status = RunStatus.IN_PROGRESS
        self.state_store.upsert(state)
        return {"run_context": ctx.model_dump(), "result": state.last_result, "status": state.status.value}
