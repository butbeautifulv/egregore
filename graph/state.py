from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class AssessmentState(TypedDict):
    raw_input: str
    sanitized_input: str
    scope: dict[str, Any]
    session_id: str
    findings: Annotated[list[dict[str, Any]], operator.add]
    critic_result: dict[str, Any] | None
    pending_approval: dict[str, Any] | None
    report: dict[str, Any] | None
    errors: Annotated[list[str], operator.add]
    approved: bool
