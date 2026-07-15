from __future__ import annotations

import structlog
from typing import Any

from cys_core.application.tools.manifest_enrichment import enrich_technique_id_from_manifest
from cys_core.domain.tools.coercion import (
    PLAYBOOK_ID_RE,
    TECHNIQUE_ID_RE,
    VALID_TI_CATEGORIES,
    coerce_tool_args,
    normalize_technique_id,
    normalize_ti_category,
)

_SIEM_INCIDENT_ID_TOOLS = frozenset({"investigate_incident", "get_incident"})
_VEIL_PLAYBOOK_ID_TOOLS = frozenset({"playbook_procedure", "playbook_get"})
_VEIL_TECHNIQUE_TOOLS = frozenset({"playbook_for_technique"})
_VEIL_TI_CATEGORY_TOOLS = frozenset(
    {"ti_search_in_category", "ti_nodes_by_category", "ti_list_kinds_in_category"}
)

_manifest_lookup: Any = None


def configure_manifest_lookup(lookup: Any) -> None:
    global _manifest_lookup
    _manifest_lookup = lookup


def _current_job_id() -> str:
    job_id = structlog.contextvars.get_contextvars().get("job_id")
    return job_id if isinstance(job_id, str) else ""


def _veil_prep_error(reason: str, message: str, tool_name: str) -> dict[str, Any]:
    return {
        "success": False,
        "error": message,
        "reason": reason,
        "source": "veil-mcp",
        "tool": tool_name,
    }


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
        enrich_technique_id_from_manifest(
            out,
            manifest_lookup=_manifest_lookup,
            job_id=_current_job_id(),
        )
    if tool_name in _VEIL_TI_CATEGORY_TOOLS:
        query = out.get("query")
        if not (isinstance(query, str) and query.strip()):
            q_alias = out.pop("q", None)
            if isinstance(q_alias, str) and q_alias.strip():
                out["query"] = q_alias.strip()
        category = out.get("category")
        if not (isinstance(category, str) and category.strip()):
            cat_alias = out.pop("cat", None)
            if isinstance(cat_alias, str) and cat_alias.strip():
                out["category"] = cat_alias.strip()
        category = normalize_ti_category(out.get("category", ""))
        query = out.get("query")
        if not category and isinstance(query, str) and query.strip():
            category = "ti"
        if category:
            out["category"] = category
    if tool_name in _VEIL_TECHNIQUE_TOOLS:
        technique_id = normalize_technique_id(out.get("technique_id", ""))
        if technique_id:
            out["technique_id"] = technique_id
    return coerce_tool_args(out)


def prepare_veil_tool_invocation(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Normalize and validate Veil MCP args before HTTP invocation."""
    normalized = normalize_veil_tool_args(tool_name, args)
    if tool_name in _VEIL_TI_CATEGORY_TOOLS:
        query = normalized.get("query")
        if not isinstance(query, str) or not query.strip():
            return _veil_prep_error(
                "invalid_args",
                "query is required and must be non-empty",
                tool_name,
            )
        normalized["query"] = query.strip()
        category = normalize_ti_category(normalized.get("category", ""))
        if not category:
            category = "ti"
        if category not in VALID_TI_CATEGORIES:
            return _veil_prep_error(
                "invalid_args",
                f"unknown category: {category}"
                + veil_ti_category_hint(tool_name, f"unknown category: {category}"),
                tool_name,
            )
        normalized["category"] = category
    if tool_name in _VEIL_PLAYBOOK_ID_TOOLS:
        playbook_id = normalized.get("id")
        if not isinstance(playbook_id, str) or not playbook_id.strip():
            return _veil_prep_error(
                "invalid_args",
                "id is required" + veil_playbook_id_hint(tool_name, "id is required"),
                tool_name,
            )
        playbook_id = playbook_id.strip()
        if not PLAYBOOK_ID_RE.match(playbook_id):
            return _veil_prep_error(
                "invalid_args",
                "id must be a slug from playbook_search (lowercase letters, digits, hyphens)"
                + veil_playbook_id_hint(tool_name, "id is required"),
                tool_name,
            )
        normalized["id"] = playbook_id
    if tool_name in _VEIL_TECHNIQUE_TOOLS:
        technique_id = normalize_technique_id(normalized.get("technique_id", ""))
        if not technique_id:
            return _veil_prep_error(
                "invalid_args",
                "technique_id is required" + veil_technique_id_hint(tool_name, "technique_id is required"),
                tool_name,
            )
        if not TECHNIQUE_ID_RE.match(technique_id):
            return _veil_prep_error(
                "invalid_args",
                f"technique_id must match ATT&CK format (e.g. T1059.001), got: {technique_id}",
                tool_name,
            )
        normalized["technique_id"] = technique_id
    return {"arguments": normalized}


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
