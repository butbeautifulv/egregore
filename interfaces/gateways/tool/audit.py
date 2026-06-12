from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bootstrap.settings import get_settings
from cys_core.infrastructure.kafka_audit import publish_audit_event_sync
from cys_core.infrastructure.kafka_topics import AUDIT_TOOL_INVOCATIONS_TOPIC
from interfaces.gateways.tool.models import ToolInvokeRequest, ToolInvokeResponse

_audit_records: list[dict[str, Any]] = []


def get_audit_records() -> list[dict[str, Any]]:
    return list(_audit_records)


def clear_audit_records() -> None:
    _audit_records.clear()


def build_audit_record(request: ToolInvokeRequest, response: ToolInvokeResponse) -> dict[str, Any]:
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "tool": request.tool_name,
        "persona": request.persona,
        "sandbox_id": request.sandbox_id,
        "job_id": request.job_id,
        "correlation_id": request.correlation_id,
        "success": response.success,
        "error": response.error,
        "args_keys": sorted(request.args.keys()),
    }


def publish_audit_record_sync(record: dict[str, Any]) -> bool:
    return publish_audit_event_sync(AUDIT_TOOL_INVOCATIONS_TOPIC, record, settings=get_settings())


def record_tool_invocation(request: ToolInvokeRequest, response: ToolInvokeResponse) -> None:
    record = build_audit_record(request, response)
    _audit_records.append(record)
    if get_settings().use_kafka:
        publish_audit_record_sync(record)
