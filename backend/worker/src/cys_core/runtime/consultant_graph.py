from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict, cast

import structlog
from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from cys_core.application.runtime_config import (
    get_consultant_research_inner_recursion,
    get_consultant_research_max_steps,
    get_consultant_synthesize_recursion_limit,
)
from cys_core.application.workers.tool_execution_tracker import consultant_ladder_complete, get_tool_outputs
from cys_core.registry.schemas import schema_registry

logger = structlog.get_logger(__name__)

_SYNTHESIZE_INSTRUCTION = (
    "Research is complete. Using ONLY the tool excerpts below, produce the structured "
    "ConsultantFinding response. Do not call tools."
)


class ConsultantGraphState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    research_steps: int
    job_id: str
    research_partial: bool


def _is_recursion_limit_error(exc: BaseException) -> bool:
    return "Recursion limit" in str(exc)


def _format_tool_context(job_id: str) -> str:
    outputs = get_tool_outputs(job_id)
    if not outputs:
        return "(no tool outputs recorded)"
    return "\n\n".join(f"### {name}\n{preview}" for name, preview in outputs)


def _resolve_job_id(state: ConsultantGraphState, default_job_id: str) -> str:
    ctx_job = structlog.contextvars.get_contextvars().get("job_id")
    if isinstance(ctx_job, str) and ctx_job:
        return ctx_job
    state_job = state.get("job_id", "")
    if state_job:
        return state_job
    return default_job_id


def build_consultant_graph(
    runtime: Any,
    defn: Any,
    *,
    model: BaseChatModel | None,
    tools: list,
    checkpointer: Any,
    store: Any,
    session_id: str,
    tenant_id: str,
    investigation_id: str,
    profile_id: str,
    goal: str,
    job_id: str = "",
):
    """Two-phase consultant graph: research (tools on) → synthesize (structured JSON only)."""
    resolved_job_id = job_id or session_id
    logger.info(
        "consultant_graph_enabled",
        job_id=resolved_job_id,
        session_id=session_id,
        investigation_id=investigation_id,
    )

    resolved_model = model or runtime.model_connector.create_model()
    schema = schema_registry.get(defn.schema_name)

    research_agent = create_agent(
        model=resolved_model,
        tools=tools,
        system_prompt=defn.system_prompt,
        middleware=runtime._build_middleware(
            defn,
            session_id,
            tenant_id=tenant_id,
            investigation_id=investigation_id,
            goal=goal or investigation_id,
            profile_id=profile_id,
        ),
        checkpointer=checkpointer,
        store=store,
        name=f"{defn.name}-research",
    )

    synthesize_agent = create_agent(
        model=resolved_model,
        tools=[],
        system_prompt=f"{defn.system_prompt}\n\n{_SYNTHESIZE_INSTRUCTION}",
        middleware=runtime._build_synthesize_middleware(
            defn,
            session_id,
            tenant_id=tenant_id,
            investigation_id=investigation_id,
            profile_id=profile_id,
        ),
        response_format=schema,
        checkpointer=checkpointer,
        store=store,
        name=f"{defn.name}-synthesize",
    )

    inner_research_limit = get_consultant_research_inner_recursion()
    synthesize_limit = get_consultant_synthesize_recursion_limit()
    max_research_steps = get_consultant_research_max_steps()

    async def research_node(state: ConsultantGraphState, config: RunnableConfig) -> dict[str, Any]:
        jid = _resolve_job_id(state, resolved_job_id)
        research_config = cast(RunnableConfig, {**config, "recursion_limit": inner_research_limit})
        messages = state["messages"]
        research_partial = False
        try:
            result = await research_agent.ainvoke({"messages": messages}, config=research_config)
            messages = result.get("messages", messages)
        except Exception as exc:
            if not _is_recursion_limit_error(exc):
                raise
            research_partial = True
            logger.info(
                "consultant_research_partial",
                job_id=jid,
                research_steps=int(state.get("research_steps", 0)) + 1,
                ladder_complete=consultant_ladder_complete(jid),
                error=str(exc)[:240],
            )

        steps = int(state.get("research_steps", 0)) + 1
        if research_partial:
            steps = max_research_steps
        logger.info(
            "consultant_research_step",
            job_id=jid,
            research_steps=steps,
            ladder_complete=consultant_ladder_complete(jid),
            research_partial=research_partial,
        )
        return {
            "messages": messages,
            "research_steps": steps,
            "job_id": jid,
            "research_partial": research_partial,
        }

    async def synthesize_node(state: ConsultantGraphState, config: RunnableConfig) -> dict[str, Any]:
        jid = _resolve_job_id(state, resolved_job_id)
        context = _format_tool_context(jid)
        synth_messages = [
            *state["messages"],
            HumanMessage(content=f"{_SYNTHESIZE_INSTRUCTION}\n\n## Research excerpts\n{context}"),
        ]
        synth_config = cast(RunnableConfig, {**config, "recursion_limit": synthesize_limit})
        return await synthesize_agent.ainvoke({"messages": synth_messages}, config=synth_config)

    def route_after_research(state: ConsultantGraphState) -> Literal["research", "synthesize"]:
        jid = _resolve_job_id(state, resolved_job_id)
        if (
            state.get("research_partial")
            or consultant_ladder_complete(jid)
            or int(state.get("research_steps", 0)) >= max_research_steps
        ):
            return "synthesize"
        return "research"

    # LangGraph accepts TypedDict state schemas at runtime; its protocol-bound generic
    # is not currently recognized by ty for Python 3.13's stdlib TypedDict.
    graph = StateGraph(cast(Any, ConsultantGraphState))
    graph.add_node("research", research_node)
    graph.add_node("synthesize", synthesize_node)
    graph.add_edge(START, "research")
    graph.add_conditional_edges(
        "research",
        route_after_research,
        {"research": "research", "synthesize": "synthesize"},
    )
    graph.add_edge("synthesize", END)
    return graph.compile(checkpointer=checkpointer, store=store)
