"""Batch evaluation backend stub — staging profile only."""

from __future__ import annotations

from typing import Any


def run_batch_eval(*, profile_id: str = "cybersec-soc", personas: list[str] | None = None) -> dict[str, Any]:
    return {
        "status": "stub",
        "profile_id": profile_id,
        "personas": personas or [],
        "message": "obs_eval_backend noop — wire Langfuse batch eval in staging",
    }
