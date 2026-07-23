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


@pytest.mark.unit
def test_active_tool_domains_defaults_to_soc_pack_domains(monkeypatch):
    from cys_core.registry import tools

    monkeypatch.delenv("PROFILE_PACK_ID", raising=False)
    assert tools._active_tool_domains() == frozenset({"veil", "siem", "nessus", "cybersec-core"})


@pytest.mark.unit
def test_active_tool_domains_empty_for_non_soc_pack(monkeypatch):
    from cys_core.registry import tools

    monkeypatch.setenv("PROFILE_PACK_ID", "general-assistant")
    assert tools._active_tool_domains() == frozenset()


@pytest.mark.unit
def test_active_tool_domains_empty_for_unknown_pack(monkeypatch):
    from cys_core.registry import tools

    monkeypatch.setenv("PROFILE_PACK_ID", "does-not-exist")
    assert tools._active_tool_domains() == frozenset()


@pytest.mark.unit
def test_tool_registry_omits_domain_tools_for_non_soc_pack(monkeypatch):
    from cys_core.registry import tools

    monkeypatch.setenv("PROFILE_PACK_ID", "general-assistant")
    registry = tools.ToolRegistry()
    domain_tool_names = {t.name for t in tools._domain_tools()}
    assert domain_tool_names == set()
    assert "web_search" in registry.names()
    # cybersec-core tools (§8.4 point 6 acceptance gap) must not leak either —
    # these were inline in _ALL_TOOLS unconditionally before this fix.
    assert "query_siem_readonly" not in registry.names()
    assert "parse_sast_report" not in registry.names()


@pytest.mark.unit
def test_tool_registry_includes_domain_tools_for_default_soc_pack(monkeypatch):
    from cys_core.registry import tools

    monkeypatch.delenv("PROFILE_PACK_ID", raising=False)
    registry = tools.ToolRegistry()
    soc_domain_tools = {t.name for t in tools._domain_tools()}
    assert soc_domain_tools
    assert soc_domain_tools <= set(registry.names())
    assert "query_siem_readonly" in registry.names()
    assert "parse_sast_report" in registry.names()
