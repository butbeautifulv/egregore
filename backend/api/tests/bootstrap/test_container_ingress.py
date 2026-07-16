from __future__ import annotations

import pytest

from bootstrap.container import Container
from bootstrap.settings import Settings


@pytest.mark.unit
def test_container_ingress_factories_share_router():
    container = Container(Settings(use_kafka=False))
    router_a = container.get_event_router()
    router_b = container.get_event_router()
    ingress_a = container.get_event_ingress()
    ingress_b = container.get_event_ingress()
    dispatch_a = container.get_dispatch_event()
    dispatch_b = container.get_dispatch_event()

    assert router_a is router_b
    assert ingress_a is ingress_b
    assert dispatch_a is dispatch_b
    assert container.get_route_and_enqueue().router is router_a
