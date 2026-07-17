from __future__ import annotations

import pytest

import cys_core.application.datasources.exec_authz as exec_authz


class _RaisingCatalog:
    def get(self, datasource_id: str):
        raise RuntimeError("catalog connection refused")


@pytest.mark.unit
def test_catalog_outage_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: a broken datasource catalog must deny access, not fall through
    to an implicit GET+LIST grant (previously a bare `except RuntimeError: pass`)."""
    monkeypatch.setattr(exec_authz, "get_datasource_catalog_port", lambda: _RaisingCatalog())
    decision = exec_authz.authorize_tool_datasource(tool_name="rag_query", persona="soc")
    assert decision is not None
    assert decision.allowed is False
    assert decision.reason == "catalog_unavailable"
