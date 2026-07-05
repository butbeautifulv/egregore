from __future__ import annotations

from interfaces.control_plane.bus_consumer import run_bus_consumer
from interfaces.control_plane.coordinator_service import get_coordinator_service


def run_coordinator_daemon(*, idle_timeout: float = 0.0) -> int:
    """Kafka consumer daemon for coordinator control plane."""
    from cys_core.observability.logging_setup import configure_logging
    from cys_core.observability.otel import setup_otel

    configure_logging("egregore-coordinator")
    setup_otel(service_name="egregore-coordinator")
    coordinator = get_coordinator_service()
    return run_bus_consumer(
        "coordinator",
        coordinator.handle_message,
        idle_timeout=idle_timeout,
        group_id="coordinator-consumer",
    )
