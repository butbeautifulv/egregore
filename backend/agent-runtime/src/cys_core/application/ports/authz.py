"""Authz port — OpenFGA ReBAC checks (ADR-005)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AuthzTuple:
    user: str
    relation: str
    object: str


@dataclass(frozen=True)
class AuthzCheck:
    user: str
    relation: str
    object: str


class AuthzPort(Protocol):
    def check(self, req: AuthzCheck) -> bool:
        """Return True if allowed. Fail-closed implementations raise on transport error when enforced."""

    def list_objects(self, *, user: str, relation: str, object_type: str) -> list[str]:
        ...

    def write_tuples(self, tuples: list[AuthzTuple]) -> None:
        ...

    def delete_tuples(self, tuples: list[AuthzTuple]) -> None:
        ...

    def ping(self) -> bool:
        """Reachability probe for health checks."""
