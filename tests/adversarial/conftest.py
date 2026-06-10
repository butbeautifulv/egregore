import os

import pytest

# Force in-memory mode for adversarial tests
os.environ.setdefault("USE_MEMORY_FALLBACK", "true")
os.environ.setdefault("STAGE", "test")


@pytest.fixture
def sanitizer():
    from cys_core.security.sanitizer import InputSanitizer

    return InputSanitizer()


@pytest.fixture
def guardrails():
    from cys_core.security.guardrails import OutputGuardrails

    return OutputGuardrails()


@pytest.fixture
def agent_bus():
    from cys_core.security.agent_bus import AgentTrustLevel, SecureAgentBus

    bus = SecureAgentBus(signing_key=b"test-signing-key")
    bus.register_agent("network", AgentTrustLevel.INTERNAL, ["critic"])
    bus.register_agent("redteam", AgentTrustLevel.PRIVILEGED, ["critic", "soc"])
    bus.register_agent("critic", AgentTrustLevel.PRIVILEGED, ["report"])
    bus.register_agent("untrusted", AgentTrustLevel.UNTRUSTED, ["critic"])
    return bus


@pytest.fixture
def scope_middleware_network():
    from cys_core.middleware.scope_middleware import ScopeMiddleware

    return ScopeMiddleware(allowed_tools={"parse_netflow", "enrich_ioc", "correlate_dns"})


@pytest.fixture
def memory():
    from cys_core.security.memory import SecureAgentMemory

    return SecureAgentMemory(user_id="test-user", signing_key=b"mem-key")
