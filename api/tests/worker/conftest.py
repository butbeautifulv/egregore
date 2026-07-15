from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from interfaces.worker.orchestrator import WorkerOrchestrator


@pytest.fixture
def worker_orchestrator(monkeypatch: pytest.MonkeyPatch) -> WorkerOrchestrator:
    from cys_core.infrastructure.queue import InMemoryJobQueue

    monkeypatch.setattr(
        "interfaces.worker.orchestrator.get_job_queue",
        lambda **kwargs: InMemoryJobQueue(),
    )
    monkeypatch.setattr(
        "interfaces.worker.orchestrator.get_container",
        lambda: MagicMock(),
    )
    return WorkerOrchestrator(
        persona="soc",
        runtime=MagicMock(),
        registry=MagicMock(),
        bus=MagicMock(),
    )
