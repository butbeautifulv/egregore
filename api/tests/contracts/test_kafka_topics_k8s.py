from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
TOPICS_JOB = REPO_ROOT / "deploy" / "k8s" / "cxado-offline" / "15-redpanda-topics-job.yaml"


@pytest.mark.unit
def test_redpanda_topics_job_uses_unified_worker_jobs_topic() -> None:
    text = TOPICS_JOB.read_text(encoding="utf-8")
    assert "worker.jobs -p 8" in text
    assert "worker.jobs.consultant" not in text
    assert "worker.jobs.soc" not in text
    assert "worker.jobs.dlq" in text
    assert "worker.jobs.paused" in text


@pytest.mark.unit
def test_redpanda_topics_job_aligns_with_kafka_topics_constant() -> None:
    from cys_core.infrastructure.kafka_topics import WORKER_JOBS_TOPIC

    text = TOPICS_JOB.read_text(encoding="utf-8")
    assert f"create {WORKER_JOBS_TOPIC} -p 8" in text
