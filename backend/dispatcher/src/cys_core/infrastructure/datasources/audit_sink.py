from __future__ import annotations

from typing import Any

_events: list[dict[str, Any]] = []


def append_datasource_audit_event(event: dict[str, Any]) -> None:
    _events.append(dict(event))


def get_datasource_audit_events() -> list[dict[str, Any]]:
    return list(_events)


def clear_datasource_audit_events() -> None:
    _events.clear()
