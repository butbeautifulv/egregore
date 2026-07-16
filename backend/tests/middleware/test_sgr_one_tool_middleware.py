from __future__ import annotations

import threading
from unittest.mock import MagicMock

import pytest

from cys_core.middleware.one_tool_middleware import OneToolPerTurnMiddleware
from cys_core.middleware.sgr_one_tool_middleware import SgrOneToolMiddleware
from cys_core.middleware.sgr_session import SgrSessionState


def _tool_request(tool_id: str, name: str = "playbook_search") -> MagicMock:
    request = MagicMock()
    request.tool_call = {"id": tool_id, "name": name, "args": {}}
    return request


@pytest.mark.unit
def test_sgr_one_tool_blocks_second_parallel_action_tool() -> None:
    session = SgrSessionState()
    middleware = SgrOneToolMiddleware(session=session)
    handler = MagicMock(return_value=MagicMock(content="ok"))
    barrier = threading.Barrier(2)
    results: list = []

    def run(tool_id: str) -> None:
        barrier.wait()
        results.append(middleware.wrap_tool_call(_tool_request(tool_id), handler))

    threads = [threading.Thread(target=run, args=(f"id-{idx}",)) for idx in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert handler.call_count == 1
    assert sum(1 for result in results if getattr(result, "status", None) == "error") == 1


@pytest.mark.unit
def test_one_tool_per_turn_blocks_second_parallel_call() -> None:
    middleware = OneToolPerTurnMiddleware()
    handler = MagicMock(return_value=MagicMock(content="ok"))
    barrier = threading.Barrier(2)
    results: list = []

    def run(tool_id: str) -> None:
        barrier.wait()
        results.append(middleware.wrap_tool_call(_tool_request(tool_id), handler))

    threads = [threading.Thread(target=run, args=(f"id-{idx}",)) for idx in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert handler.call_count == 1
    assert sum(1 for result in results if getattr(result, "status", None) == "error") == 1
