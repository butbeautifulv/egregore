from __future__ import annotations

from typing import Any


class CoordinatorProgressTracker:
    """Debounce coordinator narratives to engagement-level milestones."""

    def __init__(self) -> None:
        self._fingerprints: dict[str, str] = {}

    def _fingerprint(self, tenant_id: str, investigation_id: str) -> str | None:
        from bootstrap.container import get_container

        store = get_container().get_engagement_state_store()
        engagement = store.get(tenant_id, investigation_id)
        if engagement is None:
            return None
        completed = tuple(sorted(engagement.completed_personas))
        failed = tuple(sorted(engagement.failed_personas))
        synthesis = str(engagement.synthesis_status)
        findings_count = len(engagement.findings_summary)
        plan = tuple(engagement.planner_plan or ())
        return "|".join(
            [
                ",".join(completed),
                ",".join(failed),
                synthesis,
                str(findings_count),
                ",".join(plan),
            ]
        )

    def should_publish(self, *, tenant_id: str, investigation_id: str, sender: str) -> bool:
        key = f"{tenant_id}:{investigation_id}"
        fp = self._fingerprint(tenant_id, investigation_id)
        if fp is None:
            return True
        milestone_fp = f"{fp}|last_sender={sender}"
        previous = self._fingerprints.get(key)
        if previous == milestone_fp:
            return False
        self._fingerprints[key] = milestone_fp
        return True


_tracker: CoordinatorProgressTracker | None = None


def get_coordinator_progress_tracker() -> CoordinatorProgressTracker:
    global _tracker
    if _tracker is None:
        _tracker = CoordinatorProgressTracker()
    return _tracker
