from __future__ import annotations

import pytest

from bootstrap.container import Container
from bootstrap.settings import Settings


@pytest.mark.unit
def test_container_get_job_queue():
    container = Container(Settings(use_kafka=False))
    queue = container.get_job_queue()
    assert queue.name in {"redis", "memory"}


@pytest.mark.unit
def test_container_get_bus_transport():
    container = Container(Settings(use_kafka=False))
    transport = container.get_bus_transport()
    assert transport.name in {"redis", "memory"}


@pytest.mark.unit
def test_container_get_sandbox_connector():
    container = Container(Settings(sandbox_connector="local"))
    sandbox = container.get_sandbox_connector()
    assert sandbox.name == "local"


@pytest.mark.unit
def test_container_wires_model_provider_from_settings(monkeypatch):
    """MODEL_PROVIDER is the model-layer equivalent of AGENT_RUNNER_IMPL — Container
    construction must flip cys_core.llm's active provider, not just read the setting."""
    import cys_core.llm as llm

    monkeypatch.setenv("MODEL_PROVIDER", "model-gateway")
    try:
        Container(Settings(use_kafka=False, model_provider="model-gateway"))
        assert llm.get_model_connector().name == "model-gateway"
    finally:
        llm.configure_default_llm_provider("litellm")
