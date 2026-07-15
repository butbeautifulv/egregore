from __future__ import annotations


class ApplicationError(Exception):
    """Base class for recoverable application-layer failures."""


class PlanningFailedError(ApplicationError):
    """Manual investigation planner failed after HTTP 202 acceptance."""

    def __init__(self, event_id: str, message: str) -> None:
        super().__init__(message)
        self.event_id = event_id


class JobDependencyNotReadyError(ApplicationError):
    """Worker job blocked on upstream persona completion."""

    def __init__(self, persona: str, depends_on: str) -> None:
        super().__init__(f"dependency_not_ready:{depends_on}")
        self.persona = persona
        self.depends_on = depends_on
