from __future__ import annotations

from cys_core.domain.tools.models import ToolDefinitionView, ToolStatus

ORCHESTRATION_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "ask_user",
        "update_todos",
        "delegate_research",
        "reasoning_step",
        "reasoning_check",
        "plan_tool_calls",
        "spawn_worker",
        "extract_structured_output",
        "create_report_outline",
    }
)

ORCHESTRATION_TOOL_DEFINITIONS: list[ToolDefinitionView] = [
    ToolDefinitionView(
        name="ask_user",
        module="orchestration",
        status=ToolStatus.REAL,
        description="Clarifying question to user",
    ),
    ToolDefinitionView(
        name="update_todos",
        module="orchestration",
        status=ToolStatus.REAL,
        description="Mutate work todo list",
    ),
    ToolDefinitionView(
        name="delegate_research",
        module="orchestration",
        status=ToolStatus.REAL,
        description="Delegate sub-research",
    ),
    ToolDefinitionView(
        name="reasoning_step",
        module="orchestration",
        status=ToolStatus.REAL,
        description="SGR reasoning step",
    ),
    ToolDefinitionView(
        name="reasoning_check",
        module="orchestration",
        status=ToolStatus.REAL,
        description="Reasoning self-check",
    ),
    ToolDefinitionView(
        name="plan_tool_calls",
        module="orchestration",
        status=ToolStatus.REAL,
        description="Plan upcoming tool calls",
    ),
    ToolDefinitionView(
        name="spawn_worker",
        module="orchestration",
        status=ToolStatus.REAL,
        description="Spawn worker persona job",
    ),
    ToolDefinitionView(
        name="extract_structured_output",
        module="orchestration",
        status=ToolStatus.REAL,
        description="Extract structured output from trace",
    ),
    ToolDefinitionView(
        name="create_report_outline",
        module="orchestration",
        status=ToolStatus.REAL,
        description="Create report outline",
    ),
]
