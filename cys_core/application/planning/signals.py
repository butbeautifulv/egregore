from __future__ import annotations

from typing import Any


class PlannerSignalDetector:
    """Derive planner signals from event payload and optional intake dict."""

    def __init__(self, *, payload: dict[str, Any] | None = None, intake: dict[str, Any] | None = None) -> None:
        self._payload = dict(payload or {})
        self._intake = dict(intake or {})
        merged = {**self._payload, **self._intake}
        self._goal = str(merged.get("goal", merged.get("message", ""))).strip()
        self._blob = f"{self._goal} {merged.get('message', '')}".upper()

    @property
    def goal(self) -> str:
        return self._goal

    def incident_id_present(self) -> bool:
        for key in ("incident_id", "incident_key"):
            if str(self._payload.get(key, self._intake.get(key, ""))).strip():
                return True
        return "INC-" in self._blob

    def advisory(self) -> bool:
        blob = self._goal.lower()
        if not blob or "inc-" in blob:
            return False
        markers = (
            "расскажи",
            "как ",
            "что такое",
            "what is",
            "how to",
            "how do",
            "explain",
            "advise",
            "advice",
            "consult",
            "devsecops",
            "ci/cd",
            "best practice",
        )
        return any(marker in blob for marker in markers)

    def multi_persona(self, personas: list[str]) -> bool:
        return len(personas) > 1

    def as_dict(self, *, personas: list[str] | None = None) -> dict[str, bool]:
        return {
            "incident_id_present": self.incident_id_present(),
            "advisory": self.advisory(),
            "multi_persona": self.multi_persona(personas or []),
        }
