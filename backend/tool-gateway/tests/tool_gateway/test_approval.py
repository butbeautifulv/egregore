from __future__ import annotations

import asyncio

import pytest

from interfaces.gateways.tool.approval import (
    HitlApprovalRecord,
    clear_approval_records,
    get_approval_records,
    params_hash,
    publish_hitl_approval_sync,
    record_hitl_approval,
)


@pytest.mark.unit
def test_params_hash_stable():
    args = {"target": "example.com", "mode": "safe"}
    assert params_hash(args) == params_hash({"mode": "safe", "target": "example.com"})


@pytest.mark.unit
def test_record_hitl_approval():
    clear_approval_records()
    record = record_hitl_approval(
        actor="alice",
        tool="run_active_scan",
        persona="redteam",
        job_id="job-1",
        decision="approve",
        tool_args={"target": "lab.local"},
    )
    assert record.approval_id.startswith("appr-")
    assert len(get_approval_records()) == 1
    clear_approval_records()


@pytest.mark.unit
async def test_publish_hitl_approval_sync_schedules_task_when_loop_running(monkeypatch):
    published = []

    async def fake_publish(record: HitlApprovalRecord) -> bool:
        published.append(record.approval_id)
        return True

    monkeypatch.setattr("interfaces.gateways.tool.approval.publish_hitl_approval", fake_publish)

    record = HitlApprovalRecord(
        approval_id="appr-test",
        actor="alice",
        tool="run_active_scan",
        persona="redteam",
        job_id="job-1",
        params_hash="deadbeef",
        decision="approve",
    )
    result = publish_hitl_approval_sync(record)
    assert result is True
    # Previously this silently no-op'd instead of actually publishing when a
    # loop was already running — the real production case for every caller.
    # Give the scheduled task a tick to run rather than assuming it fired.
    await asyncio.sleep(0)
    assert published == ["appr-test"]
