from __future__ import annotations

from cys_core.application.use_cases.dispatch_event import DispatchEvent
from cys_core.application.use_cases.route_and_enqueue import RouteAndEnqueueEvent
from cys_core.domain.events.models import SecurityEvent
from tests.support.recording_trace_backend import RecordingApplicationTracing, RecordingTraceBackend


class _FakeRouter:
    def route(self, event: SecurityEvent):
        from cys_core.domain.events.models import RoutingDecision

        return RoutingDecision(event_id=event.id, personas=["soc"], playbook_id="test")


class _FakeEnqueuer:
    def enqueue_from_routing_sync(self, *args, **kwargs):
        return ["job-1"]

    async def enqueue_from_routing(self, *args, **kwargs):
        return ["job-1"]


def test_route_and_enqueue_emits_span():
    backend = RecordingTraceBackend()
    tracing = RecordingApplicationTracing(backend)
    uc = RouteAndEnqueueEvent(
        router=_FakeRouter(),
        enqueuer=_FakeEnqueuer(),
        correlation_id_port=_NoopCorrelation(),
        application_tracing=tracing,
    )
    uc.execute("siem.alert", {"message": "x"}, correlation_id="eng-1")
    assert any(name == "ingress.route_and_enqueue" for name, _ in backend.spans)


def test_dispatch_emits_span():
    backend = RecordingTraceBackend()
    tracing = RecordingApplicationTracing(backend)
    dispatch = DispatchEvent(router=_FakeRouter(), enqueuer=_FakeEnqueuer(), application_tracing=tracing)
    event = SecurityEvent(
        id="evt-1",
        type="siem.alert",
        source="test",
        severity="low",
        payload={},
        correlation_id="eng-2",
    )
    dispatch.dispatch_sync(event, {})
    assert any(name == "ingress.dispatch" for name, _ in backend.spans)


class _NoopCorrelation:
    def bind(self, correlation_id: str):
        return None

    def reset(self, token) -> None:
        _ = token
