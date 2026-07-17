from __future__ import annotations

import json
import re
from typing import Any

from cys_core.application.ports.catalog import AgentCatalogPort
from cys_core.domain.findings.models import ConductorStepResult

_catalog: AgentCatalogPort | None = None


def configure_output_schema_catalog(catalog: AgentCatalogPort) -> None:
    global _catalog
    _catalog = catalog


def detect_output_schema(goal: str, *, persona: str = "", profile_id: str = "cybersec-soc") -> str:
    del profile_id
    if persona and _catalog is not None:
        entry = _catalog.get_agent(persona)
        if entry and entry.output_schema:
            return entry.output_schema
    lower = goal.lower()
    if any(word in lower for word in ("severity", "priority", "p0", "p1")):
        return "finding"
    if "timeline" in lower:
        return "timeline"
    if "ioc" in lower or "indicator" in lower:
        return "ioc_list"
    if any(word in lower for word in ("gaia", "answer", "question")):
        return "gaia_answer"
    return "summary"


def build_structured_extraction_prompt(
    *,
    goal: str,
    schema_type: str,
    agent_summary: str,
) -> str:
    return f"""Extract a structured deliverable from the agent summary.

Goal: {goal}
Expected schema: {schema_type}

Agent summary:
{agent_summary[:8000]}

Output JSON only with keys:
- schema_type (string)
- confidence (0-100 integer)
- weaknesses (list of strings)
- payload (object matching schema_type)
"""


def parse_structured_output(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return {"raw": text.strip()}
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {"raw": text.strip()}
    if not isinstance(data, dict):
        return {"raw": text.strip()}
    return data


def merge_structured_into_result(result: dict[str, Any], structured: dict[str, Any]) -> dict[str, Any]:
    merged = dict(result)
    if isinstance(merged.get("structured_deliverable"), dict):
        return merged
    merged["structured_deliverable"] = structured
    if "ConductorStepResult" in str(type(result)) or "reply" in merged:
        payload = structured.get("payload")
        if payload and not merged.get("reply"):
            merged["reply"] = json.dumps(payload, ensure_ascii=False)
    return merged


def enrich_conductor_result(result: dict[str, Any], *, goal: str) -> dict[str, Any]:
    """Attach lightweight structured metadata to conductor output when missing."""
    if not isinstance(result, dict):
        return result
    try:
        ConductorStepResult.model_validate(result)
    except Exception:
        return result
    summary = result.get("reply", "")
    if not summary.strip():
        return result
    schema_type = detect_output_schema(goal)
    structured = {
        "schema_type": schema_type,
        "confidence": int(float(result.get("confidence", 0.0)) * 100),
        "weaknesses": [],
        "payload": {"summary": summary, "plan_delta": result.get("plan_delta", {})},
    }
    return merge_structured_into_result(result, structured)
