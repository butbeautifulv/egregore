from __future__ import annotations

from bootstrap.settings import get_settings


def should_auto_approve_dev() -> bool:
    return get_settings().stage == "dev"


def trust_threshold(profile_id: str = "cybersec-soc") -> float:
    from cys_core.infrastructure.catalog.profile_policy import get_hitl_threshold

    return float(get_hitl_threshold(profile_id))
