from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cys_core.application.ports.hitl import HitlPauseRegistry
from cys_core.domain.workers.hitl import create_approval_id, params_hash
from cys_core.domain.workers.models import PendingHitlAction

_pause_registry: HitlPauseRegistry | None = None
_publish_paused: Callable[[dict[str, Any]], None] | None = None
_on_pause_count: Callable[[int], None] | None = None


def configure(
    *,
    registry: HitlPauseRegistry,
    publish_paused: Callable[[dict[str, Any]], None],
    on_pause_count: Callable[[int], None] | None = None,
) -> None:
    global _pause_registry, _publish_paused, _on_pause_count
    _pause_registry = registry
    _publish_paused = publish_paused
    _on_pause_count = on_pause_count


def job_id_from_session(session_id: str) -> str | None:
    parts = session_id.split(":", 2)
    if len(parts) == 3 and parts[0] == "worker":
        return parts[2]
    return None


def build_hitl_preview(
    *,
    tool_name: str,
    tool_args: dict[str, Any],
    risk_level: str,
    session_id: str,
    persona: str,
) -> dict[str, Any]:
    job_id = job_id_from_session(session_id) or session_id
    approval_id = create_approval_id()
    return {
        "action": "tool_call",
        "tool": tool_name,
        "args": tool_args,
        "risk": risk_level,
        "job_id": job_id,
        "session_id": session_id,
        "persona": persona,
        "approval_id": approval_id,
        "params_hash": params_hash(tool_args),
    }


def register_hitl_pause(preview: dict[str, Any]) -> PendingHitlAction:
    if _pause_registry is None or _publish_paused is None:
        raise RuntimeError("HITL pause registry not configured; call bootstrap.container.wire_hitl_pause()")

    pending = PendingHitlAction(
        job_id=preview["job_id"],
        session_id=preview["session_id"],
        persona=preview["persona"],
        tool_name=preview["tool"],
        tool_args=preview.get("args", {}),
        risk_level=preview.get("risk", ""),
        approval_id=preview["approval_id"],
    )
    _pause_registry.pause_for_hitl(pending, preview)
    if _on_pause_count is not None:
        _on_pause_count(len(_pause_registry.list_pending_approvals()))
    _publish_paused(
        {
            "job_id": pending.job_id,
            "persona": pending.persona,
            "tool": pending.tool_name,
            "approval_id": pending.approval_id,
            "status": "awaiting_approval",
        }
    )
    return pending


def resume_decision_approved(decision: Any) -> bool:
    if isinstance(decision, dict):
        if decision.get("decision") == "reject":
            return False
        if decision.get("decision") in {"approve", "edit"}:
            return True
        decisions = decision.get("decisions", [])
        if decisions and decisions[0].get("type") == "reject":
            return False
        return True
    return bool(decision)
