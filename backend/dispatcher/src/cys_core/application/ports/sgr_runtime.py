from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field

from cys_core.domain.reasoning.sgr_models import SchemaGuidedReasoningStep


class SgrReasonThenActResult(BaseModel):
    reasoning: SchemaGuidedReasoningStep
    selected_tool: str = ""
    tool_args: dict[str, Any] = Field(default_factory=dict)


class SgrRuntimePort(Protocol):
    def reason_then_act(
        self,
        *,
        prompt: str,
        tool_names: list[str],
        schema_hint: dict[str, Any] | None = None,
    ) -> SgrReasonThenActResult: ...

