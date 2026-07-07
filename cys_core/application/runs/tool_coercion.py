from __future__ import annotations

import json
import structlog
from typing import Any

_SIEM_INCIDENT_ID_TOOLS = frozenset({"investigate_incident", "get_incident"})
_VEIL_PLAYBOOK_ID_TOOLS = frozenset({"playbook_procedure", "playbook_get"})
_VEIL_TECHNIQUE_TOOLS = frozenset({"playbook_for_technique"})
_VEIL_TI_CATEGORY_TOOLS = frozenset(
    {"ti_search_in_category", "ti_nodes_by_category", "ti_list_kinds_in_category"}
)
_TI_CATEGORY_ALIASES: dict[str, str] = {
    "ioc": "ti",
    "iocs": "ti",
    "threat_intel": "ti",
    "threat-intel": "ti",
    "threatintelligence": "ti",
    "indicator": "ti",
    "indicators": "ti",
    "cve": "vuln",
    "cves": "vuln",
    "vulnerability": "vuln",
    "vulnerabilities": "vuln",
    "attack": "mitre",
    "att&ck": "mitre",
    "mitre_attack": "mitre",
    "playbooks": "playbook",
    "skills": "playbook",
}


def _current_job_id() -> str:
    job_id = structlog.contextvars.get_contextvars().get("job_id")
    return job_id if isinstance(job_id, str) else ""


def normalize_ti_category(category: Any) -> str:
    if not isinstance(category, str):
        return ""
    cat = category.strip().lower()
    if not cat:
        return ""
    return _TI_CATEGORY_ALIASES.get(cat, cat)


def veil_ti_category_hint(tool_name: str, error: str) -> str:
    if tool_name not in _VEIL_TI_CATEGORY_TOOLS:
        return ""
    if "unknown category" not in error.lower():
        return ""
    return (
        " Hint: valid categories are ti (IOCs/actors), vuln, mitre, detection, playbook, engage, "
        "sbom, code_rules, dast, lola — use ti for IOC enrichment, not ioc."
    )


def normalize_siem_tool_args(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Normalize Qwen-style SIEM tool args before MCP invocation."""
    out = dict(args) if args else {}
    nested = out.pop("kwargs", None)
    if isinstance(nested, dict):
        for key, value in nested.items():
            out.setdefault(key, value)
    if tool_name in _SIEM_INCIDENT_ID_TOOLS:
        incident_id = out.get("incident_id")
        if not (isinstance(incident_id, str) and incident_id.strip()):
            alias = out.pop("id", None)
            if isinstance(alias, str) and alias.strip():
                out["incident_id"] = alias.strip()
    return coerce_tool_args(out)


def normalize_veil_tool_args(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Normalize Qwen-style Veil playbook tool args before MCP invocation."""
    out = dict(args) if args else {}
    nested = out.pop("kwargs", None)
    if isinstance(nested, dict):
        for key, value in nested.items():
            out.setdefault(key, value)
    if tool_name in _VEIL_PLAYBOOK_ID_TOOLS:
        playbook_id = out.get("id")
        if not (isinstance(playbook_id, str) and playbook_id.strip()):
            for alias in ("skill_id", "playbook_id", "playbook", "name"):
                alias_val = out.pop(alias, None)
                if isinstance(alias_val, str) and alias_val.strip():
                    out["id"] = alias_val.strip()
                    break
    if tool_name in _VEIL_TECHNIQUE_TOOLS:
        technique_id = out.get("technique_id")
        if not (isinstance(technique_id, str) and technique_id.strip()):
            for alias in ("technique", "mitre_technique", "mitre_id", "attack_id", "id"):
                alias_val = out.pop(alias, None)
                if isinstance(alias_val, str) and alias_val.strip():
                    out["technique_id"] = alias_val.strip()
                    break
        technique_id = out.get("technique_id")
        if not (isinstance(technique_id, str) and technique_id.strip()):
            job_id = _current_job_id()
            if job_id:
                from cys_core.application.workers.tool_execution_tracker import get_merged_manifest

                manifest = get_merged_manifest(job_id)
                if manifest is not None and manifest.suggested_mitre_techniques:
                    out["technique_id"] = manifest.suggested_mitre_techniques[0]
    if tool_name in _VEIL_TI_CATEGORY_TOOLS:
        category = normalize_ti_category(out.get("category", ""))
        query = out.get("query")
        if not category and isinstance(query, str) and query.strip():
            category = "ti"
        if category:
            out["category"] = category
    return coerce_tool_args(out)


def veil_playbook_id_hint(tool_name: str, error: str) -> str:
    if tool_name not in _VEIL_PLAYBOOK_ID_TOOLS:
        return ""
    lower = error.lower()
    if "id is required" not in lower and "validation" not in lower:
        return ""
    return " Hint: call playbook_search first, then playbook_procedure(id=<skill_id from search>)."


def veil_technique_id_hint(tool_name: str, error: str) -> str:
    if tool_name not in _VEIL_TECHNIQUE_TOOLS:
        return ""
    if "technique_id is required" not in error.lower():
        return ""
    return (
        " Hint: when SIEM has no MITRE IDs, use playbook_search(query from incident name/type); "
        "for NetworkScan use technique_id=T1046."
    )


def coerce_tool_args(args: dict[str, Any]) -> dict[str, Any]:
    """Normalize LLM tool args (string ints/bools/lists) before execution."""
    out: dict[str, Any] = {}
    for key, value in args.items():
        out[key] = _coerce_value(value)
    return out


def _coerce_value(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        lower = stripped.lower()
        if lower in ("true", "false"):
            return lower == "true"
        if stripped.isdigit():
            return int(stripped)
        if stripped.startswith("[") or stripped.startswith("{"):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return value
    if isinstance(value, dict):
        return {k: _coerce_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_coerce_value(item) for item in value]
    return value
