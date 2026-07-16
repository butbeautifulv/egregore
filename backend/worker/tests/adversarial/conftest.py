"""Adversarial tests inherit shared fixtures from tests/conftest.py."""

from __future__ import annotations

import pytest

from cys_core.middleware.scope_middleware import ScopeMiddleware
from cys_core.security.memory import SecureAgentMemory

pytestmark = pytest.mark.adversarial


@pytest.fixture
def memory() -> SecureAgentMemory:
    return SecureAgentMemory(user_id="adversarial-test-user")


@pytest.fixture
def scope_middleware_network() -> ScopeMiddleware:
    return ScopeMiddleware(
        allowed_tools={
            "enrich_ioc",
            "list_scans",
            "sync_scan_inventory",
            "lookup_asset_by_ip",
            "list_high_risk_assets",
            "playbook_search",
            "playbook_get",
            "ti_search_in_category",
        }
    )
