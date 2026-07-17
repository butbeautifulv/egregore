"""No-op and in-memory AuthzPort implementations."""

from __future__ import annotations

from cys_core.application.ports.authz import AuthzCheck, AuthzTuple


class NoopAuthzPort:
    """Always allow; used when AUTHZ_MODE=off."""

    def check(self, req: AuthzCheck) -> bool:
        return True

    def list_objects(self, *, user: str, relation: str, object_type: str) -> list[str]:
        return []

    def write_tuples(self, tuples: list[AuthzTuple]) -> None:
        return None

    def delete_tuples(self, tuples: list[AuthzTuple]) -> None:
        return None

    def ping(self) -> bool:
        return True


class InMemoryAuthzPort:
    """Tuple store for tests and local enforce without OpenFGA."""

    def __init__(self) -> None:
        self._tuples: set[tuple[str, str, str]] = set()

    def check(self, req: AuthzCheck) -> bool:
        if (req.user, req.relation, req.object) in self._tuples:
            return True
        # Simplified: owner implies editor/viewer style for tests via direct tuples only
        return False

    def list_objects(self, *, user: str, relation: str, object_type: str) -> list[str]:
        prefix = f"{object_type}:"
        return sorted(
            obj
            for u, rel, obj in self._tuples
            if u == user and rel == relation and obj.startswith(prefix)
        )

    def write_tuples(self, tuples: list[AuthzTuple]) -> None:
        for t in tuples:
            self._tuples.add((t.user, t.relation, t.object))

    def delete_tuples(self, tuples: list[AuthzTuple]) -> None:
        for t in tuples:
            self._tuples.discard((t.user, t.relation, t.object))

    def ping(self) -> bool:
        return True
