from __future__ import annotations

import pytest

from bootstrap.container import get_container


@pytest.mark.unit
def test_bus_router_singleton():
    container = get_container()
    first = container.get_bus_ingress_router()
    second = container.get_bus_ingress_router()
    assert first is second
