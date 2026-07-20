from __future__ import annotations

import json
import re
from typing import Any

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

VALID_TI_CATEGORIES = frozenset(
    {
        "ti",
        "vuln",
        "mitre",
        "detection",
        "playbook",
        "engage",
        "sbom",
        "code_rules",
        "dast",
        "lola",
    }
)

PLAYBOOK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
TECHNIQUE_ID_RE = re.compile(r"^T\d{4}(?:\.\d+)?$", re.IGNORECASE)


def normalize_technique_id(raw: Any) -> str:
    if not isinstance(raw, str):
        return ""
    tid = raw.strip().upper()
    if not tid:
        return ""
    if tid.startswith("T") and TECHNIQUE_ID_RE.match(tid):
        return tid
    if re.match(r"^\d{4}(?:\.\d+)?$", tid):
        return f"T{tid}"
    return tid


def normalize_ti_category(category: Any) -> str:
    if not isinstance(category, str):
        return ""
    cat = category.strip().lower()
    if not cat:
        return ""
    return _TI_CATEGORY_ALIASES.get(cat, cat)


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
