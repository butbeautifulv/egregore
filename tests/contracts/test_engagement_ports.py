from __future__ import annotations

from cys_core.application.bus_ingress_router import BusIngressRouter
from cys_core.infrastructure.engagement.memory_egress import MemoryEngagementEgress
from cys_core.infrastructure.engagement.noop_egress import NoopEngagementEgress


def test_engagement_egress_port_methods():
    egress = MemoryEngagementEgress()
    assert hasattr(egress, "publish_status")
    assert hasattr(egress, "publish_event")
    assert hasattr(egress, "subscribe")
    noop = NoopEngagementEgress()
    noop.publish_status("e1", "created", {})
    noop.publish_event("e1", "control", {})


def test_bus_ingress_router_methods():
    router = BusIngressRouter()
    assert hasattr(router, "route_envelope")


class _Orch:
    async def enqueue_from_bus(self, envelope) -> str:
        return "j1"

    def enqueue_from_routing_sync(self, *args, **kwargs) -> list[str]:
        return []

    async def enqueue_from_routing(self, *args, **kwargs) -> list[str]:
        return ["job-async"]


def test_orchestration_port_methods():
    orch = _Orch()
    import asyncio

    assert asyncio.run(orch.enqueue_from_bus({})) == "j1"
    assert orch.enqueue_from_routing_sync("e1", ["soc"]) == []
    assert asyncio.run(orch.enqueue_from_routing("e1", ["soc"])) == ["job-async"]
