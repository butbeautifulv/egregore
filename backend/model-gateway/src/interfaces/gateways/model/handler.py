from __future__ import annotations

from bootstrap.container import get_container
from cys_core.application.use_cases.invoke_model import ModelInvokeCommand, ModelMessage
from interfaces.gateways.model.models import ModelInvokeRequest, ModelInvokeResponse


async def invoke_model(request: ModelInvokeRequest) -> ModelInvokeResponse:
    command = ModelInvokeCommand(
        persona=request.persona,
        system_prompt=request.system_prompt,
        messages=[
            ModelMessage(
                role=m.role,
                content=m.content,
                source=m.source,
                tool_calls=m.tool_calls,
                tool_call_id=m.tool_call_id,
            )
            for m in request.messages
        ],
        system_prompt_digest=request.system_prompt_digest,
        model=request.model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        session_id=request.session_id,
        tools=request.tools,
        tool_choice=request.tool_choice,
    )
    result = await get_container().get_invoke_model().execute(command)
    return ModelInvokeResponse(
        success=result.success,
        content=result.content,
        refused=result.refused,
        refusal_reason=result.refusal_reason,
        model=result.model,
        usage=result.usage,
        error=result.error,
        tool_calls=result.tool_calls,
    )


__all__ = ["invoke_model"]
