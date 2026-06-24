import os

import pytest

os.environ.setdefault("USE_MEMORY_FALLBACK", "true")
os.environ.setdefault("STAGE", "test")


def pytest_configure(config):
    from bootstrap.container import get_container

    get_container()


@pytest.fixture
def sanitizer():
    from cys_core.domain.security.sanitizer import InputSanitizer

    return InputSanitizer()


@pytest.fixture
def guardrails():
    from cys_core.domain.security.guardrails import OutputGuardrails

    return OutputGuardrails()


@pytest.fixture
def agent_bus():
    from cys_core.domain.security.agent_bus import AgentTrustLevel, SecureAgentBus

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


@pytest.fixture
def auth_keypair():
    from tests.auth_helpers import generate_rsa_keypair

    return generate_rsa_keypair()


@pytest.fixture
def auth_settings(monkeypatch, auth_keypair):
    from bootstrap.settings import get_settings
    from cys_core.domain.security.auth_models import ROLE_GATEWAY, ROLE_INGRESS, ROLE_OPERATOR, ROLE_READER
    from cys_core.infrastructure.auth.factory import get_token_verifier
    from cys_core.infrastructure.auth.keycloak import KeycloakJwtVerifier
    from tests.auth_helpers import _StaticJWKClient, sign_access_token

    issuer = "https://keycloak.test/realms/cxado"
    monkeypatch.setenv("AUTH_ENABLED", "1")
    monkeypatch.setenv("RBAC_ENABLED", "1")
    monkeypatch.setenv("KEYCLOAK_ISSUER", issuer)
    monkeypatch.setenv("KEYCLOAK_AUDIENCE", "egregore-api")
    monkeypatch.setenv("KEYCLOAK_CLIENT_ID", "egregore-api")
    get_settings.cache_clear()
    get_token_verifier.cache_clear()

    verifier = KeycloakJwtVerifier(
        issuer=issuer,
        audience="egregore-api",
        client_id="egregore-api",
        jwks_client=_StaticJWKClient(auth_keypair),
    )
    monkeypatch.setattr(
        "cys_core.infrastructure.auth.factory.build_token_verifier",
        lambda _settings: verifier,
    )
    monkeypatch.setattr(
        "interfaces.api.auth.get_token_verifier",
        lambda: verifier,
    )

    def _token(roles: list[str]) -> str:
        return sign_access_token(auth_keypair, issuer=issuer, roles=roles)

    yield {
        "issuer": issuer,
        "token": _token,
        "roles": {
            "ingress": ROLE_INGRESS,
            "reader": ROLE_READER,
            "operator": ROLE_OPERATOR,
            "gateway": ROLE_GATEWAY,
        },
    }

    get_settings.cache_clear()
    get_token_verifier.cache_clear()
