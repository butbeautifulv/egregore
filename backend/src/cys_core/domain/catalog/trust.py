from __future__ import annotations

from typing import Any

_DECLARED_TRUST_BY_LEVEL = {
    "untrusted": 0.25,
    "internal": 0.75,
    "privileged": 0.9,
    "system": 1.0,
}


def declared_trust_score(entry: Any) -> float:
    quality = getattr(entry, "quality", None)
    if quality is not None and getattr(quality, "sample_size", 0) > 0:
        return float(quality.empirical_trust)
    trust_level = getattr(entry, "trust_level", "")
    return _DECLARED_TRUST_BY_LEVEL.get(trust_level, 0.5)
