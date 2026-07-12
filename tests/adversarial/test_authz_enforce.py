from __future__ import annotations

import pytest
from fastapi import HTTPException

from cys_core.application.authz.service import AuthzService
from cys_core.application.spawn_broker import SubagentSpawnBroker
from cys_core.domain.runs.models import ContextKind, InteractionMode, RunContext
from cys_core.domain.runs.spawn import SpawnWorkerPayload
from cys_core.infrastructure.authz.noop import NoopAuthzPort
from interfaces.api.authz_helpers import require_workspace_relation
from interfaces.api.tenant_deps import require_tenant_match_http
from cys_core.domain.security.auth_models import AuthClaims


@pytest.mark.unit
def test_tenant_bind_rejects_cross_tenant() -> None:
    auth = AuthClaims(sub="alice", organization_id="acme")
    with pytest.raises(HTTPException) as exc:
        require_tenant_match_http(auth, "other")
    assert exc.value.status_code == 403


@pytest.mark.unit
def test_empty_workspace_denied_in_enforce(monkeypatch: pytest.MonkeyPatch) -> None:
    authz = AuthzService(NoopAuthzPort(), mode="enforce")
    from unittest.mock import MagicMock

    container = MagicMock()
    container.get_authz_service.return_value = authz
    monkeypatch.setattr("interfaces.api.authz_helpers.get_container", lambda: container)
    with pytest.raises(HTTPException):
        require_workspace_relation(AuthClaims(sub="u1"), None, "", "can_view")


@pytest.mark.unit
def test_spawn_requires_workspace_in_enforce() -> None:
    from unittest.mock import MagicMock

    catalog = MagicMock()
    conductor = MagicMock()
    conductor.capabilities = ["intel"]
    agent = MagicMock()
    agent.enabled = True
    agent.profile_id = "cybersec-soc"
    agent.quality.empirical_trust = 1.0

    def get_agent(name: str):
        if name == "conductor":
            return conductor
        return agent

    catalog.get_agent.side_effect = get_agent
    broker = SubagentSpawnBroker(catalog, require_workspace_in_enforce=True)
    payload = SpawnWorkerPayload(
        parent_context=RunContext(
            context_id="ctx-1",
            kind=ContextKind.SESSION,
            tenant_id="default",
            mode=InteractionMode.AGENT,
        ),
        persona="intel",
        sub_goal="test",
    )
    reason = broker.validate(payload, mode=InteractionMode.AGENT, parent_persona="conductor", workspace_id="")
    assert reason == "workspace_required_in_enforce"
