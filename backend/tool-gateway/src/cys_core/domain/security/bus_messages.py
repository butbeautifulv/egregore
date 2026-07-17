from __future__ import annotations

from enum import StrEnum


class BusMessageType(StrEnum):
    FINDING = "finding"
    DELEGATE = "delegate"
    REVISION = "revision"
    ESCALATION = "escalation"
    CONTROL = "control"
    REPORT = "report"


# Backward-compatible aliases for existing string literals
MESSAGE_FINDING = BusMessageType.FINDING.value
MESSAGE_DELEGATE = BusMessageType.DELEGATE.value
MESSAGE_REVISION = BusMessageType.REVISION.value
MESSAGE_ESCALATION = BusMessageType.ESCALATION.value
MESSAGE_CONTROL = BusMessageType.CONTROL.value
MESSAGE_REPORT = BusMessageType.REPORT.value
