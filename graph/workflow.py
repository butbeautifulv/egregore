from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from cys_core.persistence import PersistenceStack, get_persistence
from graph.nodes import (
    critic_node,
    dispatch_node,
    hitl_gate_node,
    ingest_node,
    report_node,
    run_agent_node,
)
from graph.state import AssessmentState

_compiled_graph = None


def build_assessment_graph(persistence: PersistenceStack | None = None):
    """Compile LangGraph security assessment pipeline."""
    global _compiled_graph
    if _compiled_graph is not None and persistence is None:
        return _compiled_graph

    stack = persistence or get_persistence()
    graph = StateGraph(AssessmentState)
    graph.add_node("ingest", ingest_node)
    graph.add_node("run_agent", run_agent_node)
    graph.add_node("critic", critic_node)
    graph.add_node("hitl_gate", hitl_gate_node)
    graph.add_node("report", report_node)

    graph.add_edge(START, "ingest")
    graph.add_conditional_edges("ingest", dispatch_node)
    graph.add_edge("run_agent", "critic")
    graph.add_edge("critic", "hitl_gate")
    graph.add_edge("hitl_gate", "report")
    graph.add_edge("report", END)

    compiled = graph.compile(checkpointer=stack.checkpointer)
    if persistence is None:
        _compiled_graph = compiled
    return compiled


def run_assessment(
    user_input: str,
    *,
    thread_id: str = "assessment-001",
    scope: dict[str, Any] | None = None,
    persistence: PersistenceStack | None = None,
    resume: bool | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run full assessment pipeline."""
    graph = build_assessment_graph(persistence)
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 25}

    if resume is not None:
        result = graph.invoke(Command(resume=resume), config=config)
        return dict(result)

    initial: AssessmentState = {
        "raw_input": user_input,
        "sanitized_input": "",
        "scope": scope or {"authorized": True},
        "session_id": thread_id,
        "findings": [],
        "critic_result": None,
        "pending_approval": None,
        "report": None,
        "errors": [],
        "approved": False,
    }
    result = graph.invoke(initial, config=config)
    return dict(result)
