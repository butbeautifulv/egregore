from __future__ import annotations

import re

# SIEM incident type / name / correlation-rule markers → MITRE ATT&CK technique IDs.
_TYPE_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("networkscan", "port_scan", "port scan", "network scan"), "T1046"),
    (("phishing", "ksmg_message", "ksmg_potential_phishing"), "T1566"),
    (("unauthorizedaccess", "failed_access", "failed access"), "T1078"),
    (("hacktoolsdetection", "malicious_pipe", "kata_taa"), "T1055"),
)

_TECHNIQUE_ID = re.compile(r"\bT\d{4}(?:\.\d{3})?\b", re.I)


def _normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _match_rules(corpus: str) -> list[str]:
    normalized = _normalize_token(corpus)
    if not normalized:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for markers, technique_id in _TYPE_RULES:
        if any(marker in normalized for marker in markers):
            if technique_id not in seen:
                seen.add(technique_id)
                found.append(technique_id)
    for match in _TECHNIQUE_ID.findall(corpus):
        tid = match.upper()
        if tid not in seen:
            seen.add(tid)
            found.append(tid)
    return found


def infer_suggested_mitre_techniques(
    *,
    incident_type: str = "",
    incident_name: str = "",
    correlation_rules: list[str] | None = None,
) -> list[str]:
    """Infer MITRE technique IDs from SIEM incident metadata when explicit IDs are absent."""
    parts: list[str] = []
    if incident_type:
        parts.append(incident_type)
    if incident_name:
        parts.append(incident_name)
    if correlation_rules:
        parts.extend(correlation_rules)
    return _match_rules(" ".join(parts))
