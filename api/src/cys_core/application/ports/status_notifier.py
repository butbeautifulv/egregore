from __future__ import annotations

from typing import Any, Protocol


class InvestigationStatusNotifierPort(Protocol):
    """Legacy status feed notifier (dual-write during egress migration)."""

    def record_investigation_update(self, payload: dict[str, Any]) -> None: ...
