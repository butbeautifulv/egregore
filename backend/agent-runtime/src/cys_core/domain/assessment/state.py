from __future__ import annotations

from typing import Any, TypedDict


class AssessmentState(TypedDict):
    raw_input: str
    sanitized_input: str
    scope: dict[str, Any]
    session_id: str
    findings: list[dict[str, Any]]
    critic_result: dict[str, Any] | None
    pending_approval: dict[str, Any] | None
    report: dict[str, Any] | None
    errors: list[str]
    approved: bool
