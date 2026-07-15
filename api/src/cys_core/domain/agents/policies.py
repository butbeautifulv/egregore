from __future__ import annotations


def build_interrupt_on(hitl_tools: dict[str, bool]) -> dict[str, dict[str, list[str]]]:
    """Build HumanInTheLoopMiddleware interrupt_on config from agent.yaml hitl_tools."""
    interrupt_on = {
        tool_name: {"allowed_decisions": ["approve", "edit", "reject"]}
        for tool_name, enabled in hitl_tools.items()
        if enabled
    }
    return interrupt_on
