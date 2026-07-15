from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field


class ReflexionLesson(BaseModel):
    investigation_id: str
    tenant_id: str = "default"
    lesson: str
    source: str = "trace_critic"


class ReflexionStorePort(Protocol):
    def append(self, lesson: ReflexionLesson) -> None: ...

    def list_for_investigation(self, tenant_id: str, investigation_id: str, *, limit: int = 5) -> list[str]: ...
