from __future__ import annotations

import re

CREDENTIAL_TECHNIQUE_PREFIXES = ("T1003",)


def slug_observation_value(value: str) -> str:
    cleaned = re.sub(r"[^\w.\-]+", "_", value.strip().lower())
    return cleaned[:80] or "unknown"


def build_obs_id(kind: str, value: str, event_uuid: str | None = None) -> str:
    if event_uuid:
        return f"obs:evt:{event_uuid}:{kind}:{slug_observation_value(value)}"
    return f"obs:{kind}:{slug_observation_value(value)}"


def parse_obs_id(obs_id: str) -> tuple[str | None, str | None, str]:
    parts = obs_id.split(":")
    if len(parts) < 3 or parts[0] != "obs":
        return None, None, ""
    if parts[1] == "evt" and len(parts) >= 5:
        return parts[2], parts[3], ":".join(parts[4:])
    return None, parts[1], ":".join(parts[2:])
