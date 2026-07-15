from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class WorkOrderIntake(BaseModel):
    goal: str = ""
    incident_id: str = ""
    alert_ids: list[str] = Field(default_factory=list)
    iocs: list[str] = Field(default_factory=list)
    log_refs: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)

    @field_validator("alert_ids", "iocs", "log_refs", mode="before")
    @classmethod
    def _coerce_str_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value.strip() else []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    def normalized_goal(self) -> str:
        return self.goal.strip()
