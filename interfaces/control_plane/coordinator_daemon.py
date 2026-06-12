from __future__ import annotations

from interfaces.control_plane.bus_consumer import run_bus_consumer
from interfaces.control_plane.coordinator_service import get_coordinator_service


def run_coordinator_daemon(*, idle_timeout: float = 0.0) -> int:
    """Kafka consumer daemon for coordinator control plane."""
    coordinator = get_coordinator_service()
    return run_bus_consumer(
        "coordinator",
        coordinator.handle_message,
        idle_timeout=idle_timeout,
        group_id="coordinator-consumer",
    )
