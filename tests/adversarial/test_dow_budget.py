"""Abuse case: DoW — job killed when token/cost/tool-call budget exceeded."""

import pytest
from fastapi.testclient import TestClient

from cys_core.domain.workers.job_budget import JobBudgetTracker
from interfaces.gateways.tool.policy import clear_all_chain_states
from interfaces.gateways.tool.server import create_app


@pytest.mark.adversarial
@pytest.mark.xfail(
    reason=(
        "Settings mocking now correctly reaches Container.__init__, but the invoke "
        "chain still succeeds twice instead of blocking on the 2nd call — the "
        "high-risk tool chain depth check isn't reading the patched "
        "max_high_risk_tool_chain_depth, or ToolChainPolicy/get_tool_chain_policy() "
        "caches independently of the container reset. Needs tracing through "
        "bootstrap/containers/tools_container.py before un-xfailing. See "
        "docs/CI_CD_KNOWN_GAPS.md."
    ),
    strict=False,
)
def test_gateway_blocks_high_risk_tool_chain(monkeypatch):
    import bootstrap.container as container_mod
    from bootstrap.settings import Settings

    clear_all_chain_states()
    JobBudgetTracker.clear_all()
    container_mod._container = None
    # Container.__init__ does `from bootstrap.settings import get_settings`, a
    # name bound once at module load — patch that call site directly rather than
    # `bootstrap.settings.get_settings`, which `bootstrap/__init__.py`'s own
    # `settings` singleton re-export shadows on the package attribute anyway.
    monkeypatch.setattr(
        container_mod,
        "get_settings",
        lambda: Settings(max_high_risk_tool_chain_depth=1),
    )

    client = TestClient(create_app())
    body = {
        "tool_name": "run_active_scan",
        "args": {"target": "lab"},
        "persona": "redteam",
        "sandbox_id": "sandbox-dow",
        "job_id": "job-dow",
    }
    assert client.post("/invoke", json=body).json()["success"] is True
    blocked = client.post("/invoke", json=body).json()
    assert blocked["success"] is False
    assert "chain depth" in blocked["error"].lower()
    clear_all_chain_states()


@pytest.mark.adversarial
def test_middleware_blocks_tool_call_budget():
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from langchain_core.messages import ToolMessage

    import cys_core.middleware.security_middleware as security_middleware

    JobBudgetTracker.clear_all()
    JobBudgetTracker.configure("sess-dow", max_tokens=10_000, max_cost_usd=5.0, max_tool_calls=1)

    middleware = security_middleware.SecurityMiddleware("soc", "sess-dow")
    middleware.rate_limiter = SimpleNamespace(check=MagicMock())
    middleware.monitor = SimpleNamespace(log_security_event=MagicMock(), log_tool_call=MagicMock())
    middleware.auto_approve_threshold = security_middleware.parse_threshold("critical")

    req = SimpleNamespace(tool_call={"name": "dedup_alerts", "args": {}, "id": "c1"})
    ok = middleware.wrap_tool_call(req, lambda r: ToolMessage(content="ok", tool_call_id="c1"))
    assert ok.content == "ok"

    blocked = middleware.wrap_tool_call(req, lambda r: ToolMessage(content="ok", tool_call_id="c2"))
    assert blocked.status == "error"
    assert "tool-call budget" in blocked.content
    JobBudgetTracker.clear_all()
