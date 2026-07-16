from __future__ import annotations

from typing import Any

from cys_core.domain.work_order.intake import WorkOrderIntake


def normalize_intake_to_event_payload(intake: dict[str, Any] | WorkOrderIntake) -> dict[str, Any]:
    model = intake if isinstance(intake, WorkOrderIntake) else WorkOrderIntake.model_validate(intake)
    payload: dict[str, Any] = {
        "goal": model.normalized_goal(),
        "message": model.normalized_goal(),
        "intake": model.model_dump(),
    }
    if model.incident_id:
        payload["incident_id"] = model.incident_id
    if model.alert_ids:
        payload["alert_ids"] = list(model.alert_ids)
    if model.iocs:
        payload["iocs"] = list(model.iocs)
    if model.log_refs:
        payload["log_refs"] = list(model.log_refs)
    if model.context:
        payload["context"] = dict(model.context)
    return payload


def intake_memory_content(intake: dict[str, Any]) -> str:
    import json

    return json.dumps(intake, ensure_ascii=False, indent=2)
