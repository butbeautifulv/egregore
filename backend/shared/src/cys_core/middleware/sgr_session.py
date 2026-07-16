from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cys_core.domain.reasoning.sgr_models import REASONING_STEP_TOOL, SchemaGuidedReasoningStep


@dataclass
class SgrSessionState:
  """Per-agent-session SGR turn state."""

  reasoning_done: bool = False
  action_tools_this_turn: int = 0
  last_reasoning: SchemaGuidedReasoningStep | None = None
  metadata: dict[str, Any] = field(default_factory=dict)

  def mark_reasoning(self, step: SchemaGuidedReasoningStep) -> None:
    self.reasoning_done = True
    self.last_reasoning = step
    self.metadata["sgr"] = step.model_dump()

  def reset_turn(self) -> None:
    self.reasoning_done = False
    self.action_tools_this_turn = 0

  def is_reasoning_tool(self, tool_name: str) -> bool:
    return tool_name == REASONING_STEP_TOOL
