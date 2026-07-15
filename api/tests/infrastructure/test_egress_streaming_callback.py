from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from cys_core.application.ports.stream_context import StreamContext
from cys_core.infrastructure.observability.egress_streaming_callback import EgressStreamingCallback


class _RecordingEgress:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, dict[str, Any]]] = []

    def publish_event(self, engagement_id: str, event_type: str, payload: dict[str, Any]) -> None:
        self.events.append((engagement_id, event_type, payload))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_egress_streaming_callback_batches_deltas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cys_core.infrastructure.observability.egress_streaming_callback.get_stream_agent_output",
        lambda: True,
    )
    settings = MagicMock()
    settings.egress_batch_seconds = 0.05
    monkeypatch.setattr(
        "cys_core.infrastructure.observability.egress_streaming_callback.get_settings",
        lambda: settings,
    )
    egress = _RecordingEgress()
    ctx = StreamContext(
        engagement_id="eng-1",
        job_id="job-1",
        persona="soc",
        tenant_id="default",
    )
    callback = EgressStreamingCallback(ctx, egress=egress)

    await callback.on_llm_new_token("hel")
    await callback.on_llm_new_token("lo")
    await asyncio.sleep(0.06)

    delta_events = [e for e in egress.events if e[1] == "assistant_delta"]
    assert len(delta_events) == 1
    assert delta_events[0][2]["delta"] == "hello"
    assert delta_events[0][2]["seq"] == 1

    await callback.on_llm_end(MagicMock(generations=[[MagicMock(generation_info={})]]))
    done_events = [e for e in egress.events if e[1] == "assistant_done"]
    assert len(done_events) == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_egress_streaming_callback_noop_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cys_core.infrastructure.observability.egress_streaming_callback.get_stream_agent_output",
        lambda: False,
    )
    egress = _RecordingEgress()
    ctx = StreamContext(engagement_id="eng-2", job_id="job-2", persona="soc")
    callback = EgressStreamingCallback(ctx, egress=egress)

    await callback.on_llm_new_token("x")
    await asyncio.sleep(0.06)
    await callback.on_llm_end(MagicMock(generations=[[MagicMock(generation_info={})]]))

    assert egress.events == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_egress_streaming_callback_publishes_each_token_when_batch_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "cys_core.infrastructure.observability.egress_streaming_callback.get_stream_agent_output",
        lambda: True,
    )
    settings = MagicMock()
    settings.egress_batch_seconds = 0.0
    monkeypatch.setattr(
        "cys_core.infrastructure.observability.egress_streaming_callback.get_settings",
        lambda: settings,
    )
    egress = _RecordingEgress()
    ctx = StreamContext(engagement_id="eng-1", job_id="job-1", persona="soc", tenant_id="default")
    callback = EgressStreamingCallback(ctx, egress=egress)

    await callback.on_llm_new_token("a")
    await callback.on_llm_new_token("b")

    delta_events = [e for e in egress.events if e[1] == "assistant_delta"]
    assert len(delta_events) == 2
    assert [e[2]["delta"] for e in delta_events] == ["a", "b"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_egress_streaming_callback_tool_events_name_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cys_core.infrastructure.observability.egress_streaming_callback.get_stream_agent_output",
        lambda: True,
    )
    monkeypatch.setattr(
        "cys_core.infrastructure.observability.egress_streaming_callback.get_stream_agent_tools",
        lambda: True,
    )
    egress = _RecordingEgress()
    ctx = StreamContext(engagement_id="eng-3", job_id="job-3", persona="hunter")
    callback = EgressStreamingCallback(ctx, egress=egress)
    run_id = uuid4()

    await callback.on_tool_start({"name": "query_siem_readonly"}, "", run_id=run_id)
    await callback.on_tool_end("result body", run_id=run_id)

    types = [e[1] for e in egress.events]
    assert types == ["tool_start", "tool_done"]
    assert egress.events[0][2]["tool_name"] == "query_siem_readonly"
    assert egress.events[0][2]["tool_call_id"] == str(run_id)
    assert egress.events[1][2].get("output_preview") == "result body"
    assert egress.events[1][2]["tool_call_id"] == str(run_id)
    assert egress.events[1][2]["ok"] is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_egress_streaming_callback_playbook_search_tool_args(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cys_core.infrastructure.observability.egress_streaming_callback.get_stream_agent_output",
        lambda: True,
    )
    monkeypatch.setattr(
        "cys_core.infrastructure.observability.egress_streaming_callback.get_stream_agent_tools",
        lambda: True,
    )
    egress = _RecordingEgress()
    ctx = StreamContext(engagement_id="eng-pb", job_id="job-pb", persona="hunter")
    callback = EgressStreamingCallback(ctx, egress=egress)
    run_id = uuid4()

    await callback.on_tool_start(
        {"name": "playbook_search"},
        "",
        run_id=run_id,
        inputs={"kwargs": {"query": "disk imaging", "limit": 5}},
    )

    assert egress.events[0][1] == "tool_start"
    payload = egress.events[0][2]
    assert payload["tool_call_id"] == str(run_id)
    assert payload["tool_args"] == {"query": "disk imaging", "limit": 5}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_egress_streaming_callback_reasoning_delta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cys_core.infrastructure.observability.egress_streaming_callback.get_stream_agent_output",
        lambda: True,
    )
    egress = _RecordingEgress()
    ctx = StreamContext(engagement_id="eng-r", job_id="job-r", persona="soc")
    callback = EgressStreamingCallback(ctx, egress=egress)
    run_id = uuid4()

    await callback.on_tool_start(
        {"name": "reasoning_step"},
        "",
        run_id=run_id,
        inputs={
            "reasoning_steps": ["Check SIEM context", "Plan triage"],
            "current_situation": "Incident ID known",
            "plan_status": "in_progress",
            "task_completed": False,
        },
    )

    types = [e[1] for e in egress.events]
    assert types == ["reasoning_delta"]
    payload = egress.events[0][2]
    assert payload["current_situation"] == "Incident ID known"
    assert payload["reasoning_steps"] == ["Check SIEM context", "Plan triage"]
    assert "tool_start" not in types


@pytest.mark.unit
@pytest.mark.asyncio
async def test_egress_streaming_callback_chat_model_end_publishes_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cys_core.infrastructure.observability.egress_streaming_callback.get_stream_agent_output",
        lambda: True,
    )
    egress = _RecordingEgress()
    ctx = StreamContext(engagement_id="eng-4", job_id="job-4", persona="planner")
    callback = EgressStreamingCallback(ctx, egress=egress)
    response = ChatResult(generations=[ChatGeneration(message=AIMessage(content='{"personas":["soc"]}'))])

    await callback.on_chat_model_end(response)

    deltas = [e for e in egress.events if e[1] == "assistant_delta"]
    assert len(deltas) == 1
    assert '{"personas":["soc"]}' in deltas[0][2]["delta"]
    assert any(e[1] == "assistant_done" for e in egress.events)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_egress_streaming_callback_empty_content_no_delta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cys_core.infrastructure.observability.egress_streaming_callback.get_stream_agent_output",
        lambda: True,
    )
    egress = _RecordingEgress()
    ctx = StreamContext(engagement_id="eng-5", job_id="job-5", persona="soc")
    callback = EgressStreamingCallback(ctx, egress=egress)
    response = ChatResult(generations=[ChatGeneration(message=AIMessage(content=""))])

    await callback.on_chat_model_end(response)

    assert not [e for e in egress.events if e[1] == "assistant_delta"]
    assert any(e[1] == "assistant_done" for e in egress.events)
