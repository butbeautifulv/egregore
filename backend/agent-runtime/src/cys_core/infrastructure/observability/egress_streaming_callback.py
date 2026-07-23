from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler, BaseCallbackHandler
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult, LLMResult

from cys_core.application.ports.engagement_egress import EngagementEgressPort
from cys_core.application.ports.stream_context import StreamContext
from cys_core.application.runtime_config import get_stream_agent_output, get_stream_agent_tools
from cys_core.application.workers.tool_execution_tracker import record_tool_execution
from cys_core.infrastructure.config.infra_settings import get_egress_streaming_settings
from cys_core.infrastructure.engagement.factory import get_engagement_egress


def _tool_output_preview(output: Any) -> str:
    text = output if isinstance(output, str) else str(output or "")
    text = text.strip()
    if not text:
        return ""
    preview_max = get_egress_streaming_settings().output_preview_max
    if len(text) <= preview_max:
        return text
    return f"{text[:preview_max]}…"


def _unwrap_tool_inputs(inputs: dict[str, Any] | None, input_str: str) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if isinstance(inputs, dict):
        payload.update(inputs)
    if not payload and input_str.strip().startswith("{"):
        try:
            parsed = json.loads(input_str)
            if isinstance(parsed, dict):
                payload = parsed
        except json.JSONDecodeError:
            return {}
    nested = payload.pop("kwargs", None)
    if isinstance(nested, dict):
        for key, value in nested.items():
            payload.setdefault(key, value)
    return payload


def _playbook_search_tool_args(inputs: dict[str, Any] | None, input_str: str) -> dict[str, Any] | None:
    raw = _unwrap_tool_inputs(inputs, input_str)
    out: dict[str, Any] = {}
    query = raw.get("query")
    if isinstance(query, str) and query.strip():
        out["query"] = query.strip()
    limit = raw.get("limit")
    if isinstance(limit, bool):
        pass
    elif isinstance(limit, int):
        out["limit"] = limit
    elif isinstance(limit, str) and limit.isdigit():
        out["limit"] = int(limit)
    subdomain = raw.get("subdomain")
    if isinstance(subdomain, str) and subdomain.strip():
        out["subdomain"] = subdomain.strip()
    return out or None

def _parse_reasoning_inputs(inputs: dict[str, Any] | None, input_str: str) -> dict[str, Any] | None:
    payload: dict[str, Any] = {}
    if isinstance(inputs, dict):
        payload.update(inputs)
    if not payload and input_str.strip().startswith("{"):
        try:
            parsed = json.loads(input_str)
            if isinstance(parsed, dict):
                payload = parsed
        except json.JSONDecodeError:
            return None
    if not payload:
        return None
    steps = payload.get("reasoning_steps")
    if not isinstance(steps, list):
        steps = []
    return {
        "current_situation": str(payload.get("current_situation", "")),
        "plan_status": str(payload.get("plan_status", "")),
        "reasoning_steps": [str(step) for step in steps if str(step).strip()],
        "task_completed": bool(payload.get("task_completed", False)),
        "enough_data": bool(payload.get("enough_data", False)),
    }


def _message_content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    if content:
        return str(content)
    return ""


def _iter_generations(response: LLMResult | ChatResult):
    for item in response.generations or []:
        if isinstance(item, list):
            yield from item
        else:
            yield item


def _extract_generation_text(response: LLMResult | ChatResult) -> str:
    parts: list[str] = []
    for gen in _iter_generations(response):
        message = getattr(gen, "message", None)
        if isinstance(message, BaseMessage):
            text = _message_content_text(message.content)
        elif isinstance(gen, ChatGeneration) and isinstance(gen.message, AIMessage):
            text = _message_content_text(gen.message.content)
        else:
            text = str(getattr(gen, "text", "") or "")
        if text:
            parts.append(text)
    return "\n".join(parts)


class EgressStreamingCallback(AsyncCallbackHandler):
    """Publish operator-only LLM/tool stream events to engagement egress."""

    def __init__(
        self,
        context: StreamContext,
        *,
        egress: EngagementEgressPort | None = None,
    ) -> None:
        super().__init__()
        self._context = context
        self._egress = egress or get_engagement_egress()
        self._buffer = ""
        self._seq = 0
        self._flush_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()
        self._tool_names: dict[UUID, str] = {}
        self._streamed_this_turn = False

    def _base_payload(self) -> dict[str, Any]:
        return {
            "tenant_id": self._context.tenant_id,
            "job_id": self._context.job_id,
            "persona": self._context.persona,
        }

    def _publish(self, event_type: str, payload: dict[str, Any]) -> None:
        self._egress.publish_event(self._context.engagement_id, event_type, payload)

    def _publish_text_delta(self, text: str) -> None:
        if not text:
            return
        self._seq += 1
        self._publish(
            "assistant_delta",
            {**self._base_payload(), "delta": text, "seq": self._seq},
        )

    async def on_llm_new_token(self, token: str | list[str | dict[str, Any]], **kwargs: Any) -> None:
        if not isinstance(token, str):
            # Multimodal content-block streaming (list of str/dict chunks) —
            # this callback only publishes plain-text deltas, not supported here.
            return
        if not get_stream_agent_output():
            return
        self._streamed_this_turn = True
        if get_egress_streaming_settings().batch_seconds <= 0:
            self._publish_text_delta(token)
            return
        async with self._lock:
            self._buffer += token
            if self._flush_task is None or self._flush_task.done():
                self._flush_task = asyncio.create_task(self._flush_after_delay())

    async def on_chat_model_stream(self, chunk: Any, **kwargs: Any) -> None:
        if not get_stream_agent_output():
            return
        content = getattr(chunk, "content", None)
        if content:
            await self.on_llm_new_token(_message_content_text(content), **kwargs)

    async def _flush_after_delay(self) -> None:
        await asyncio.sleep(get_egress_streaming_settings().batch_seconds)
        await self._flush_buffer()

    async def _flush_buffer(self) -> None:
        async with self._lock:
            if not self._buffer:
                return
            delta = self._buffer
            self._buffer = ""
            self._seq += 1
            seq = self._seq
        self._publish(
            "assistant_delta",
            {**self._base_payload(), "delta": delta, "seq": seq},
        )

    async def _cancel_flush_task(self) -> None:
        if self._flush_task is not None and not self._flush_task.done():
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

    async def _finalize_turn(self, response: LLMResult | ChatResult, **kwargs: Any) -> None:
        if not get_stream_agent_output():
            return
        await self._cancel_flush_task()
        await self._flush_buffer()
        if not self._streamed_this_turn:
            text = _extract_generation_text(response)
            if text:
                self._publish_text_delta(text)
        self._streamed_this_turn = False
        finish_reason = None
        for gen in _iter_generations(response):
            generation_info = getattr(gen, "generation_info", {}) or {}
            if isinstance(generation_info, dict):
                finish_reason = generation_info.get("finish_reason")
            break
        payload = self._base_payload()
        if finish_reason:
            payload["finish_reason"] = finish_reason
        self._publish("assistant_done", payload)

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        await self._finalize_turn(response, **kwargs)

    async def on_chat_model_end(self, response: ChatResult, **kwargs: Any) -> None:
        await self._finalize_turn(response, **kwargs)

    async def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        tool_name = str(serialized.get("name") or serialized.get("id") or "tool")
        self._tool_names[run_id] = tool_name
        record_tool_execution(self._context.job_id)
        if tool_name == "reasoning_step":
            reasoning = _parse_reasoning_inputs(inputs, input_str)
            if reasoning and get_stream_agent_output():
                self._publish("reasoning_delta", {**self._base_payload(), **reasoning})
            return
        if not get_stream_agent_tools():
            return
        payload = {**self._base_payload(), "tool_name": tool_name, "tool_call_id": str(run_id)}
        if tool_name == "load_skill":
            from cys_core.registry.skills_tool import _parse_skill_name_from_inputs

            skill_name = _parse_skill_name_from_inputs(inputs, input_str)
            if skill_name:
                payload["skill_name"] = skill_name
        if tool_name == "playbook_search":
            tool_args = _playbook_search_tool_args(inputs, input_str)
            if tool_args:
                payload["tool_args"] = tool_args
        self._publish("tool_start", payload)

    async def on_tool_end(self, output: str, *, run_id: UUID, **kwargs: Any) -> None:
        if not get_stream_agent_tools():
            return
        tool_name = self._tool_names.pop(run_id, "tool")
        payload: dict[str, Any] = {
            **self._base_payload(),
            "tool_name": tool_name,
            "tool_call_id": str(run_id),
            "ok": True,
        }
        preview = _tool_output_preview(output)
        if preview:
            payload["output_preview"] = preview
        self._publish("tool_done", payload)

    async def on_tool_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        if not get_stream_agent_tools():
            return
        tool_name = self._tool_names.pop(run_id, "tool")
        self._publish(
            "tool_error",
            {
                **self._base_payload(),
                "tool_name": tool_name,
                "tool_call_id": str(run_id),
                "error": str(error),
            },
        )


def build_egress_streaming_callbacks(context: StreamContext) -> list[BaseCallbackHandler]:
    if not get_stream_agent_output():
        return []
    return [EgressStreamingCallback(context)]


def publish_assistant_snapshot(
    *,
    engagement_id: str,
    job_id: str,
    persona: str,
    tenant_id: str,
    text: str,
    egress: EngagementEgressPort | None = None,
) -> None:
    from cys_core.application.engagement_streaming import publish_assistant_snapshot as _publish

    sink = egress or get_engagement_egress()
    _publish(
        egress=sink,
        engagement_id=engagement_id,
        job_id=job_id,
        persona=persona,
        tenant_id=tenant_id,
        text=text,
    )
