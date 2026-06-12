from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.infrastructure.k8s_sandbox import K8sSandboxConnector


@pytest.mark.unit
def test_k8s_sandbox_creates_and_deletes_job():
    batch_api = MagicMock()
    connector = K8sSandboxConnector(namespace="cys-agi", batch_api=batch_api)
    creds = connector.create("run-1", "soc")
    assert creds.sandbox_id.startswith("k8s-worker-soc-run-1")
    assert batch_api.create_namespaced_job.called
    connector.destroy("run-1")
    batch_api.delete_namespaced_job.assert_called_once()


@pytest.mark.unit
def test_k8s_sandbox_falls_back_without_api():
    connector = K8sSandboxConnector(batch_api=None)
    creds = connector.create("run-2", "network")
    assert "fallback" in creds.sandbox_id
    connector.destroy("run-2")
