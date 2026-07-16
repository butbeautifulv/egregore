from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from cys_core.domain.tools.models import ToolInvokeCommand, ToolInvokeResult
from cys_core.infrastructure.kafka_audit import publish_audit_event_sync
from cys_core.infrastructure.kafka_topics import AUDIT_TOOL_INVOCATIONS_TOPIC

_audit_records: list[dict[str, Any]] = []
_use_kafka: bool = False
_settings: Any = None


def configure_tool_audit(*, use_kafka: bool, settings: Any) -> None:
    global _use_kafka, _settings
    _use_kafka = use_kafka
    _settings = settings


def get_audit_records() -> list[dict[str, Any]]:
    return list(_audit_records)


def clear_audit_records() -> None:
    _audit_records.clear()


def build_audit_record(command: ToolInvokeCommand, result: ToolInvokeResult) -> dict[str, Any]:
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "tool": command.tool_name,
        "persona": command.persona,
        "sandbox_id": command.sandbox_id,
        "job_id": command.job_id,
        "correlation_id": command.correlation_id,
        "success": result.success,
        "error": result.error,
        "args_keys": sorted(command.args.keys()),
    }


def publish_audit_record_sync(record: dict[str, Any]) -> bool:
    if _settings is None:
        return False
    return publish_audit_event_sync(AUDIT_TOOL_INVOCATIONS_TOPIC, record, settings=_settings)


def record_tool_invocation(command: ToolInvokeCommand, result: ToolInvokeResult) -> None:
    record = build_audit_record(command, result)
    _audit_records.append(record)
    if _use_kafka:
        publish_audit_record_sync(record)
