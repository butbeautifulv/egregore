from __future__ import annotations

import ast
import json
import re
from typing import Any

_PREFIX_RE = re.compile(
    r"^(?:returning\s+structured\s+response|here\s+is\s+the\s+plan|"
    r"structured\s+response|plan\s*:)\s*[:\-]?\s*",
    re.IGNORECASE,
)
_PERSONAS_RE = re.compile(r"personas\s*=\s*(\[[^\]]*\])", re.IGNORECASE)
_SUB_GOALS_RE = re.compile(r"sub_goals\s*=\s*(\{(?:[^{}]|\{[^{}]*\})*\})", re.IGNORECASE)
_RATIONALE_RE = re.compile(r"rationale\s*=\s*('(?:\\'|[^'])*'|\"(?:\\\"|[^\"])*\")", re.IGNORECASE)
_EXEC_MODE_RE = re.compile(r"execution_mode\s*=\s*([A-Za-z_]+|None|'[^']*'|\"[^\"]*\")", re.IGNORECASE)
_SYNTHESIS_RE = re.compile(
    r"synthesis_persona\s*=\s*([A-Za-z_]+|None|'[^']*'|\"[^\"]*\")",
    re.IGNORECASE,
)


def parse_json_text(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return parsed
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        fenced = "\n".join(lines).strip()
        try:
            parsed = json.loads(fenced)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _literal(value: str) -> Any:
    try:
        return ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return None


def _strip_prefixes(text: str) -> str:
    stripped = text.strip()
    while True:
        updated = _PREFIX_RE.sub("", stripped, count=1).strip()
        if updated == stripped:
            return stripped
        stripped = updated


def parse_loose_structured_text(text: str) -> dict[str, Any] | None:
    """Parse JSON, fenced JSON, or Python-repr planner blobs."""
    if not text or not str(text).strip():
        return None

    direct = parse_json_text(text)
    if direct is not None:
        return direct

    stripped = _strip_prefixes(str(text))
    if stripped != text:
        direct = parse_json_text(stripped)
        if direct is not None:
            return direct

    # Try whole blob as Python literal dict after normalizing key=value pairs.
    if "personas=" in stripped and "personas" not in stripped[:20]:
        # Convert common key=value form into a dict-like literal when possible.
        pass

    personas_m = _PERSONAS_RE.search(stripped)
    if not personas_m:
        return None

    personas = _literal(personas_m.group(1))
    if not isinstance(personas, list):
        return None

    result: dict[str, Any] = {"personas": [str(item) for item in personas]}

    sub_m = _SUB_GOALS_RE.search(stripped)
    if sub_m:
        sub_goals = _literal(sub_m.group(1))
        if isinstance(sub_goals, dict):
            result["sub_goals"] = {str(k): str(v) for k, v in sub_goals.items()}

    rat_m = _RATIONALE_RE.search(stripped)
    if rat_m:
        rationale = _literal(rat_m.group(1))
        if rationale is not None:
            result["rationale"] = str(rationale)

    exec_m = _EXEC_MODE_RE.search(stripped)
    if exec_m:
        raw_mode = exec_m.group(1)
        if raw_mode in {"None", "none"}:
            result["execution_mode"] = None
        else:
            mode = _literal(raw_mode)
            if mode is not None:
                result["execution_mode"] = str(mode)

    syn_m = _SYNTHESIS_RE.search(stripped)
    if syn_m:
        raw_syn = syn_m.group(1)
        if raw_syn in {"None", "none"}:
            result["synthesis_persona"] = None
        else:
            syn = _literal(raw_syn)
            if syn is not None:
                result["synthesis_persona"] = str(syn)

    return result
