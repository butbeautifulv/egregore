from __future__ import annotations

import pytest

from interfaces.gateways.tool.approval import (
    clear_approval_records,
    get_approval_records,
    params_hash,
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
