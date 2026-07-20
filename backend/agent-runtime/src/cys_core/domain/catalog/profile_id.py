from __future__ import annotations

from typing import Any, Protocol

DEFAULT_PROFILE_ID = "cybersec-soc"
"""Legacy default profile id for cybersec-soc product pack.

Prefer explicit `profile_id` on events, catalog entries, and ProductProfilePack.
Scheduled for deprecation once all ingress paths pass profile_id explicitly.
"""


class _ProfileIdCarrier(Protocol):
    profile_id: str


def resolve_profile_id(
    *,
    explicit: str | None = None,
    payload: dict[str, Any] | None = None,
    catalog_entry: _ProfileIdCarrier | None = None,
) -> str:
    if explicit:
        return explicit
    if payload and payload.get("profile_id"):
        return str(payload["profile_id"])
    if catalog_entry is not None and getattr(catalog_entry, "profile_id", ""):
        return catalog_entry.profile_id
    return DEFAULT_PROFILE_ID
