from __future__ import annotations

import interfaces.worker.orchestrator as orchestrator_mod


def test_orchestrator_module_does_not_import_worker_job_span():
    assert "worker_job_span" not in orchestrator_mod.__dict__
