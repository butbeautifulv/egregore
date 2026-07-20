from __future__ import annotations

from typing import Any


def read_repo_metadata(repo_path: str) -> dict[str, Any]:
    return {
        "repo_path": repo_path,
        "languages": ["python", "yaml"],
        "default_branch": "main",
        "ci": "github_actions",
    }


def parse_sast_report(report_json: str) -> dict[str, Any]:
    import json

    try:
        data = json.loads(report_json) if report_json.strip().startswith("{") else {"raw": report_json}
    except json.JSONDecodeError:
        data = {"raw": report_json[:2000]}
    return {"parsed_findings": data, "count": len(str(data))}


def analyze_workflow(workflow_yaml: str) -> dict[str, Any]:
    risks = []
    lower = workflow_yaml.lower()
    if "pull_request_target" in lower:
        risks.append("pull_request_target usage detected")
    if "aws_access_key" in lower or "secret" in lower:
        risks.append("secrets referenced in workflow environment")
    return {"risks": risks or ["no obvious workflow risks in stub"]}


def run_active_scan(target: str) -> dict[str, Any]:
    from cys_core.integrations.veneno_mcp_client import call_veneno_mcp_tool, veneno_mcp_enabled

    if veneno_mcp_enabled():
        return call_veneno_mcp_tool("run_active_scan", {"target": target})
    return {
        "status": "simulated",
        "target": target,
        "note": "PoC analysis only; enable VENENO_MCP_ENABLED for execution",
    }


def parse_netflow(netflow_text: str) -> dict[str, Any]:
    return {
        "source": "netflow_stub",
        "indicators": ["periodic_tls", "non_browser_traffic"] if "90s" in netflow_text else [],
        "raw_excerpt": netflow_text[:500],
    }


def enrich_ioc(ioc: str) -> dict[str, Any]:
    from cys_core.integrations.veil_mcp_client import call_veil_mcp_tool, veil_mcp_enabled

    if veil_mcp_enabled():
        result = call_veil_mcp_tool("ti_search_in_category", {"query": ioc, "category": "ti", "limit": 5})
        if result.get("success"):
            return {"ioc": ioc, "source": "veil-mcp", "enrichment": result.get("content")}
        return {"ioc": ioc, "source": "veil-mcp", "error": result.get("error", "Veil enrichment failed")}
    return {"ioc": ioc, "reputation": "suspicious", "tags": ["stub"], "source": "stub"}


def correlate_dns(dns_events: str) -> dict[str, Any]:
    _ = dns_events
    return {"pattern": "periodic_lookup", "confidence": 0.7}


def dedup_alerts(alerts_text: str) -> dict[str, Any]:
    _ = alerts_text
    return {"deduplicated_count": 1, "clusters": ["powershell_encoded"]}


def build_timeline(events_text: str) -> dict[str, Any]:
    _ = events_text
    return {"timeline": ["T+0 EDR alert", "T+2m proxy anomaly", "T+10m dedup repeat"]}


def correlate_findings(findings_json: str) -> dict[str, Any]:
    _ = findings_json
    return {"correlated": True, "priority": "P2"}


def check_control(framework: str, control_id: str, evidence: str) -> dict[str, Any]:
    return {
        "framework": framework,
        "control_id": control_id,
        "status": "partial",
        "gaps": ["missing quarterly access review"] if "60%" in evidence else [],
    }


def map_framework(observation: str) -> dict[str, Any]:
    _ = observation
    return {"framework": "SOC2", "controls": ["CC6.1", "CC7.2"]}


def audit_evidence(evidence_text: str) -> dict[str, Any]:
    _ = evidence_text
    return {"auditability": "partial", "ticket_coverage": "60%"}


def execute_command(command: str) -> dict[str, Any]:
    return {"executed": command, "status": "denied_by_policy"}


def plan_tool_calls(goal: str, steps_json: str) -> dict[str, Any]:
    import json

    try:
        steps = json.loads(steps_json) if steps_json.strip().startswith("[") else []
    except json.JSONDecodeError:
        steps = []
    return {"goal": goal, "planned_steps": steps, "status": "planned"}


def create_report_outline(title: str, sections_json: str = "[]") -> dict[str, Any]:
    import json

    try:
        sections = json.loads(sections_json) if sections_json.strip().startswith("[") else []
    except json.JSONDecodeError:
        sections = []
    if not sections:
        sections = ["summary", "findings", "recommendations"]
    return {"title": title, "sections": sections}


def browser_use(url: str, action: str = "navigate") -> dict[str, Any]:
    from cys_core.application.runtime_config import get_browser_enabled
    from cys_core.security.monitor import AgentMonitor

    AgentMonitor("conductor").log_orchestration_tool("browser", "browser_use", {"url": url, "action": action})
    if not get_browser_enabled():
        return {"success": False, "error": "browser disabled", "hint": "set BROWSER_ENABLED=true with HITL"}
    return {"success": False, "stub": True, "url": url, "action": action}


def transcribe_audio(path: str) -> dict[str, Any]:
    return {"success": False, "path": path, "note": "STT stub — integrate Whisper or cloud STT"}
