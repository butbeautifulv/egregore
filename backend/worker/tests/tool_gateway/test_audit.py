from __future__ import annotations

import pytest

from interfaces.gateways.tool.audit import build_audit_record, clear_audit_records, get_audit_records
from interfaces.gateways.tool.models import ToolInvokeRequest, ToolInvokeResponse
from tests.tool_gateway.gateway_client import GatewayTestClient


@pytest.mark.unit
def test_build_audit_record_shape():
    request = ToolInvokeRequest(
        tool_name="dedup_alerts",
        args={"alerts_text": "x"},
        persona="soc",
        sandbox_id="sandbox-1",
        job_id="job-1",
    )
    response = ToolInvokeResponse(success=True, tool_name="dedup_alerts")
    record = build_audit_record(request, response)
    assert record["tool"] == "dedup_alerts"
    assert record["persona"] == "soc"
    assert record["success"] is True
    assert record["args_keys"] == ["alerts_text"]


@pytest.mark.unit
def test_gateway_records_audit_on_invoke():
    clear_audit_records()
    client = GatewayTestClient()
    client.post(
        "/invoke",
        json={
            "tool_name": "query_siem_readonly",
            "args": {"query": "dns tunnel"},
            "persona": "soc",
            "sandbox_id": "sandbox-audit",
            "job_id": "job-audit",
        },
    )
    records = get_audit_records()
    assert len(records) == 1
    assert records[0]["tool"] == "query_siem_readonly"
    assert records[0]["job_id"] == "job-audit"
    clear_audit_records()
