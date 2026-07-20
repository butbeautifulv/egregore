from __future__ import annotations

import json

import pytest


@pytest.mark.unit
def test_all_tool_functions_and_registry_edges():
    from cys_core.registry import tools

    assert json.loads(tools.read_repo_metadata.invoke({"repo_path": "/repo"}))["default_branch"] == "main"
    assert json.loads(tools.parse_sast_report.invoke({"report_json": '{"a": 1}'}))["parsed_findings"] == {"a": 1}
    plain = json.loads(tools.parse_sast_report.invoke({"report_json": "plain text"}))
    assert plain["parsed_findings"]["raw"] == "plain text"
    assert "raw" in json.loads(tools.parse_sast_report.invoke({"report_json": "{not-json"}))["parsed_findings"]

    risky = json.loads(
        tools.analyze_workflow.invoke({"workflow_yaml": "on: pull_request_target\nenv:\n  secret: ${{ secrets.X }}"})
    )
    assert len(risky["risks"]) == 2
    assert json.loads(tools.analyze_workflow.invoke({"workflow_yaml": "name: ci"}))["risks"] == [
        "no obvious workflow risks in stub"
    ]
    assert json.loads(tools.run_active_scan.invoke({"target": "example.com"}))["status"] == "simulated"
    assert json.loads(tools.parse_netflow.invoke({"netflow_text": "beacon every 90s"}))["indicators"]
    assert json.loads(tools.parse_netflow.invoke({"netflow_text": "normal"}))["indicators"] == []
    assert json.loads(tools.enrich_ioc.invoke({"ioc": "1.2.3.4"}))["reputation"] == "suspicious"
    assert json.loads(tools.correlate_dns.invoke({"dns_events": "events"}))["confidence"] == 0.7
    siem = json.loads(tools.query_siem_readonly.invoke({"query": "powershell", "time_range": "1h"}))
    assert siem["readonly"] is True
    assert siem["query"] == "powershell"
    assert json.loads(tools.dedup_alerts.invoke({"alerts_text": "alerts"}))["deduplicated_count"] == 1
    assert json.loads(tools.build_timeline.invoke({"events_text": "events"}))["timeline"]
    assert json.loads(tools.correlate_findings.invoke({"findings_json": "[]"}))["correlated"] is True
    assert json.loads(tools.check_control.invoke({"framework": "SOC2", "control_id": "CC6", "evidence": "60%"}))["gaps"]
    assert (
        json.loads(tools.check_control.invoke({"framework": "SOC2", "control_id": "CC6", "evidence": "complete"}))[
            "gaps"
        ]
        == []
    )
    assert json.loads(tools.map_framework.invoke({"observation": "mfa"}))["framework"] == "SOC2"
    assert json.loads(tools.audit_evidence.invoke({"evidence_text": "tickets"}))["ticket_coverage"] == "60%"
    assert json.loads(tools.execute_command.invoke({"command": "id"}))["status"] == "denied_by_policy"
    with pytest.raises(KeyError, match="Unknown tool"):
        tools.tool_registry.get("missing")
