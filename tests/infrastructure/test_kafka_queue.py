from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cys_core.infrastructure.kafka_queue import KafkaJobQueue, _worker_job_topics


@pytest.mark.unit
def test_worker_job_topics_from_personas() -> None:
    with patch("cys_core.application.resource_source.get_resource_source") as mock_src:
        mock_src.return_value.list_worker_personas.return_value = ["consultant", "soc", "critic"]
        topics = _worker_job_topics()
    assert topics == [
        "worker.jobs.consultant",
        "worker.jobs.soc",
        "worker.jobs.critic",
    ]


@pytest.mark.unit
def test_kafka_queue_persona_none_uses_multi_topics() -> None:
    queue = KafkaJobQueue(persona=None, bootstrap_servers="localhost:19092")
    with patch.object(queue, "_consumer_topics", return_value=["worker.jobs.consultant", "worker.jobs.soc"]):
        assert queue._consumer_group_id() == "egregore-workers"
        assert queue._consumer_topics() == ["worker.jobs.consultant", "worker.jobs.soc"]


@pytest.mark.unit
def test_kafka_queue_persona_scoped_single_topic() -> None:
    queue = KafkaJobQueue(persona="consultant", bootstrap_servers="localhost:19092")
    assert queue._consumer_topics() == ["worker.jobs.consultant"]
    assert queue._consumer_group_id() == "workers-consultant"
