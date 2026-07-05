from __future__ import annotations

from typing import Any

from cys_core.application.runtime_config import get_engagement_async_planning
from cys_core.domain.events.models import SecurityEvent

ASYNC_PLANNER_PENDING = "async_planner_pending"


def is_meta_llm_engagement(event: SecurityEvent) -> bool:
    return event.type == "engagement.start" and str(event.payload.get("plan_strategy", "")) == "meta_llm"


def use_async_engagement_planner(event: SecurityEvent, payload: dict[str, Any]) -> bool:
    """Async 202 for meta-LLM engagements when ENGAGEMENT_ASYNC_PLANNING is enabled."""
    _ = payload
    if not is_meta_llm_engagement(event):
        return False
    return get_engagement_async_planning()
