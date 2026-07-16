"""Adversarial tests inherit shared fixtures from tests/conftest.py."""

from __future__ import annotations

import pytest

from cys_core.domain.security.agent_bus import AgentTrustLevel, SecureAgentBus
from cys_core.domain.security.guardrails import OutputGuardrails
from cys_core.domain.security.sanitizer import InputSanitizer

pytestmark = pytest.mark.adversarial


@pytest.fixture
def sanitizer() -> InputSanitizer:
    return InputSanitizer()


@pytest.fixture
def guardrails() -> OutputGuardrails:
    return OutputGuardrails()


@pytest.fixture
def agent_bus() -> SecureAgentBus:
    bus = SecureAgentBus(signing_key=b"adversarial-bus-key")
    bus.register_agent("network", AgentTrustLevel.INTERNAL, ["critic"])
    bus.register_agent("critic", AgentTrustLevel.PRIVILEGED, ["report"])
    bus.register_agent("untrusted", AgentTrustLevel.UNTRUSTED, ["critic"])
    bus.register_agent("report", AgentTrustLevel.PRIVILEGED, [])
    return bus
