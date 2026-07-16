from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage

from cys_core.application.ports.sgr_runtime import SgrReasonThenActResult
from cys_core.application.reasoning.tool_instantiator import ToolInstantiator
from cys_core.domain.reasoning.sgr_models import REASONING_STEP_TOOL, SchemaGuidedReasoningStep
from cys_core.llm.reasoning import get_reasoning_model_connector


class SgrHybridRuntime:
    """Minimal 'real' SGR hybrid: call a separate reasoning model to pick next tool + args.

    This is intentionally lightweight: it doesn't replace LangGraph planning; it provides a
    deterministic **reason->select_tool->instantiate_args** step using the REASONING_MODEL.
    """

    def __init__(self) -> None:
        self._instantiator = ToolInstantiator()

    def reason_then_act(
        self,
        *,
        prompt: str,
        tool_names: list[str],
        schema_hint: dict[str, Any] | None = None,
    ) -> SgrReasonThenActResult:
        model = get_reasoning_model_connector().create_model()
        tool_list = ", ".join(tool_names)
        hint = f"\nSchema hint: {schema_hint}" if schema_hint else ""
        reasoning_prompt = (
            "You are a schema-guided reasoning controller.\n"
            f"First produce a {REASONING_STEP_TOOL}-compatible JSON object.\n"
            "Then output a single JSON object with keys: tool_name, tool_args.\n"
            f"Allowed tool_name values: [{tool_list}].\n"
            f"{hint}\n\n"
            f"User/task:\n{prompt}\n"
        )
        resp = model.invoke([HumanMessage(content=reasoning_prompt)])
        text = getattr(resp, "content", "") if resp is not None else ""

        reasoning = self._instantiator.parse_with_retry(
            lambda p: getattr(model.invoke([HumanMessage(content=p)]), "content", ""),
            SchemaGuidedReasoningStep,
            initial_prompt=reasoning_prompt,
            max_retries=3,
        )
        try:
            import json

            parsed = json.loads(text) if isinstance(text, str) and text.strip().startswith("{") else {}
        except Exception:
            parsed = {}
        tool_name = str(parsed.get("tool_name", "")) if isinstance(parsed, dict) else ""
        tool_args = parsed.get("tool_args", {}) if isinstance(parsed, dict) else {}
        if tool_name not in tool_names:
            tool_name = ""
            tool_args = {}
        if not isinstance(tool_args, dict):
            tool_args = {}
        return SgrReasonThenActResult(reasoning=reasoning, selected_tool=tool_name, tool_args=tool_args)

