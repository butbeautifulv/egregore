from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import pytest

from cys_core.application.authz.service import AuthzService
from cys_core.domain.security.auth_models import AuthClaims


class _SlowAuthzPort:
    """Fake AuthzPort whose check() simulates a blocking OpenFGA network round-trip.

    OpenFgaAuthzPort.check() (cys_core/infrastructure/authz/openfga.py) is a
    plain sync method that internally bridges to the OpenFGA SDK's async
    client via asyncio.run()/future.result(), i.e. it always blocks the
    calling thread for the duration of the HTTP round-trip.
    """

    def check(self, req) -> bool:
        time.sleep(0.2)
        return True

    def list_objects(self, *, user: str, relation: str, object_type: str) -> list[str]:
        return []

    def write_tuples(self, tuples) -> None:
        return None

    def delete_tuples(self, tuples) -> None:
        return None

    def ping(self) -> bool:
        return True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_require_relation_dependency_offloads_blocking_authz_check(monkeypatch) -> None:
    """require_relation()'s FastAPI dependency must not block the event loop.

    It runs on every authz-checked API request. If it called authz.check()
    directly instead of via asyncio.to_thread, it would stall the whole
    FastAPI event loop (all concurrent requests) for the duration of each
    OpenFGA round-trip -- the same bug class as WorkerJobFinalizer's
    synchronous psycopg.connect() inside async def (already fixed in
    cys_core/application/workers/job_finalizer.py).
    """
    from interfaces.api import authz_deps

    container = SimpleNamespace(
        get_authz_service=lambda: AuthzService(_SlowAuthzPort(), mode="enforce"),
    )
    monkeypatch.setattr(authz_deps, "get_container", lambda: container)

    dependency = authz_deps.require_relation("workspace", "can_view", "workspace_id")
    request = SimpleNamespace(path_params={"workspace_id": "ws-1"})
    auth = AuthClaims(sub="alice")

    ticks = 0

    async def ticker() -> None:
        nonlocal ticks
        for _ in range(20):
            await asyncio.sleep(0.02)
            ticks += 1

    ticker_task = asyncio.create_task(ticker())
    await dependency(request, auth, None)
    ticks_during_check = ticks
    ticker_task.cancel()

    # If authz.check() ran synchronously on the event loop, the ticker task
    # would never be scheduled until the dependency returned, so
    # ticks_during_check would be 0 (mirrors the reproduction used for the
    # FollowUpAggregator fix in tests/application/workers/test_follow_up_spawn.py).
    assert ticks_during_check >= 3
