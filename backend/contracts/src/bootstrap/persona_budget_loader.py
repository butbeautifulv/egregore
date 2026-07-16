from __future__ import annotations

import json
from typing import TYPE_CHECKING

from cys_core.domain.workers.models import PersonaBudget

if TYPE_CHECKING:
    from bootstrap.settings import Settings

_cached: dict[str, PersonaBudget] | None = None


def load_persona_budgets(settings: Settings) -> dict[str, PersonaBudget]:
    """Merge PERSONA_BUDGETS_OVERRIDES_JSON over static defaults and cache the result."""
    global _cached
    from cys_core.domain.policy.defaults import _BASE_PERSONA_BUDGETS

    merged = dict(_BASE_PERSONA_BUDGETS)
    raw = (settings.persona_budgets_overrides_json or "").strip()
    if raw:
        try:
            overrides = json.loads(raw)
        except json.JSONDecodeError:
            overrides = None
        if isinstance(overrides, dict):
            for persona, data in overrides.items():
                if not isinstance(persona, str) or not isinstance(data, dict):
                    continue
                base = merged.get(persona)
                merged[persona] = PersonaBudget(
                    max_tokens=int(data.get("max_tokens", base.max_tokens if base else 40_000)),
                    max_cost_usd=float(data.get("max_cost_usd", base.max_cost_usd if base else 2.0)),
                    max_tool_calls=int(
                        data.get("max_tool_calls", base.max_tool_calls if base else 50)
                    ),
                )
    _cached = merged
    return dict(merged)


def get_loaded_persona_budgets() -> dict[str, PersonaBudget]:
    if _cached is not None:
        return dict(_cached)
    from cys_core.domain.policy.defaults import _BASE_PERSONA_BUDGETS

    return dict(_BASE_PERSONA_BUDGETS)


def reset_persona_budget_cache() -> None:
    global _cached
    _cached = None
