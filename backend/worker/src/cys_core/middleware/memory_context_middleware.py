from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Awaitable

from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage

from cys_core.domain.memory.services import MemoryReadService
from cys_core.domain.security.prompt_context import wrap_investigation_memory
from cys_core.middleware._framework_casts import cast_model_response
from cys_core.observability.metrics import metrics


class MemoryContextMiddleware(AgentMiddleware):
    """Inject investigation episodic memory into model context as untrusted data."""

    def __init__(
        self,
        memory_reader: MemoryReadService,
        *,
        tenant_id: str = "default",
        investigation_id: str = "",
        max_entries: int = 10,
        max_chars: int = 4000,
    ) -> None:
        super().__init__()
        self.memory_reader = memory_reader
        self.tenant_id = tenant_id
        self.investigation_id = investigation_id
        self.max_entries = max_entries
        self.max_chars = max_chars
        self.entries_loaded = 0

    def _inject_memory(self, request: ModelRequest) -> list[AnyMessage]:
        if not self.investigation_id:
            return list(request.messages)
        entries = self.memory_reader.query_investigation(
            self.tenant_id,
            self.investigation_id,
            limit=self.max_entries,
            requesting_tenant_id=self.tenant_id,
        )
        self.entries_loaded = len(entries)
        metrics.record_memory_read(self.tenant_id, entries_loaded=len(entries))
        if not entries:
            return list(request.messages)
        block = wrap_investigation_memory(
            self.memory_reader.format_for_prompt(entries, max_chars=self.max_chars),
        )
        memory_message = HumanMessage(content=block)
        return [*request.messages, memory_message]

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse | AIMessage:
        updated = request.override(messages=self._inject_memory(request))
        return handler(updated)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse] | ModelResponse],
    ) -> ModelResponse | AIMessage:
        updated = request.override(messages=self._inject_memory(request))
        result = handler(updated)
        if inspect.isawaitable(result):
            return cast_model_response(await result)
        return cast_model_response(result)
