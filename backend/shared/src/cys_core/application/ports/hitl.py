from __future__ import annotations

from typing import Any, Protocol

from cys_core.domain.workers.models import PendingHitlAction


class HitlPauseRegistry(Protocol):
    """Port for pausing worker jobs pending human approval."""

    def pause_for_hitl(self, pending: PendingHitlAction, preview: dict[str, Any]) -> None: ...

    def list_pending_approvals(self) -> list[Any]: ...
