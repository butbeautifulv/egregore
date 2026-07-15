from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from cys_core.application.ports.sgr_runtime import SgrReasonThenActResult
from cys_core.application.reasoning.sgr_iron_metrics import _metrics
from cys_core.application.reasoning.sgr_iron_policy import check_iron_tool_allowed
from cys_core.application.reasoning.tool_instantiator import ToolInstantiator
from cys_core.domain.reasoning.sgr_models import REASONING_STEP_TOOL, SchemaGuidedReasoningStep
from cys_core.llm.reasoning import get_reasoning_model_connector


class IronToolSelection(BaseModel):
    tool_name: str = Field(description="One of the allowed tool names")
    rationale: str = Field(max_length=200)


class SgrIronRuntime:
    """Iron SGR: structured reasoning step + tool name selection + arg instantiation."""

    def __init__(self, *, max_retries: int = 3) -> None:
        self._instantiator = ToolInstantiator()
        self._max_retries = max_retries

    def reason_then_act(
        self,
        *,
        prompt: str,
        tool_names: list[str],
        profile_id: str = "default",
        policy=None,
        schema_hint: dict[str, Any] | None = None,
    ) -> SgrReasonThenActResult:
        action_tools = [t for t in tool_names if t != REASONING_STEP_TOOL]
        model = get_reasoning_model_connector().create_model()

        reasoning_prompt = (
            "Produce schema-guided reasoning as JSON matching reasoning_step fields.\n"
            f"Task:\n{prompt}\n"
        )
        reasoning = self._instantiator.parse_with_retry(
            lambda p: str(getattr(model.invoke([HumanMessage(content=p)]), "content", "")),
            SchemaGuidedReasoningStep,
            initial_prompt=reasoning_prompt,
            max_retries=self._max_retries,
        )

        selector_prompt = (
            "Select exactly one tool to invoke next.\n"
            f"Allowed tools: {', '.join(action_tools)}\n"
            f"{self._instantiator.schema_to_prompt(IronToolSelection)}\n"
            f"Context:\n{reasoning.model_dump_json()}\n"
        )
        selection = self._instantiator.parse_with_retry(
            lambda p: str(getattr(model.invoke([HumanMessage(content=p)]), "content", "")),
            IronToolSelection,
            initial_prompt=selector_prompt,
            max_retries=self._max_retries,
        )
        tool_name = selection.tool_name.strip()
        decision = check_iron_tool_allowed(
            tool_name=tool_name,
            allowed_tools=action_tools,
            mode="sgr_iron",
            profile_id=profile_id,
            policy=policy,
        )
        if not decision.allowed:
            _metrics().record_sgr_iron_parse_retry()
            return SgrReasonThenActResult(reasoning=reasoning, selected_tool="", tool_args={})

        args_prompt = (
            f"Instantiate JSON arguments for tool '{tool_name}'.\n"
            f"Task context:\n{prompt}\n"
            f"Reasoning:\n{reasoning.model_dump_json()}\n"
            "Return JSON object with key tool_args mapping to argument dict.\n"
        )
        try:
            import json

            raw = str(getattr(model.invoke([HumanMessage(content=args_prompt)]), "content", ""))
            parsed = json.loads(raw) if raw.strip().startswith("{") else {}
            tool_args = parsed.get("tool_args", parsed) if isinstance(parsed, dict) else {}
            if not isinstance(tool_args, dict):
                tool_args = {}
        except Exception:
            _metrics().record_sgr_iron_parse_retry()
            tool_args = {}

        return SgrReasonThenActResult(
            reasoning=reasoning,
            selected_tool=tool_name,
            tool_args=tool_args,
        )
