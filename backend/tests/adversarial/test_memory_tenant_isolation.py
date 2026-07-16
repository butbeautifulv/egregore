"""Abuse case: tenant A cannot read tenant B episodic memory."""

from __future__ import annotations

import pytest

from cys_core.domain.memory.services import MemoryReadService, MemoryWriteService
from cys_core.infrastructure.memory.stores import InMemoryEpisodicMemoryStore


@pytest.mark.adversarial
def test_cross_tenant_memory_read_blocked():
    store = InMemoryEpisodicMemoryStore()
    writer = MemoryWriteService(store)
    reader = MemoryReadService(store)

    writer.append_finding(
        tenant_id="tenant-a",
        investigation_id="inv-1",
        source_agent="soc",
        source_job_id="job-1",
        finding={"secret": "tenant-a-data"},
        trust_score=0.9,
    )

    leaked = reader.query_investigation(
        "tenant-a",
        "inv-1",
        requesting_tenant_id="tenant-b",
    )
    assert leaked == []
