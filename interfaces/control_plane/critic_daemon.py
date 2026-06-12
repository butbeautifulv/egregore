from __future__ import annotations

from interfaces.control_plane.bus_consumer import run_bus_consumer
from interfaces.control_plane.critic_service import get_critic_service


def run_critic_daemon(*, idle_timeout: float = 0.0) -> int:
    """Kafka consumer daemon for critic control plane."""
    critic = get_critic_service()
    return run_bus_consumer("critic", critic.handle_message, idle_timeout=idle_timeout, group_id="critic-consumer")
