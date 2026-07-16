from __future__ import annotations

import structlog

from cys_core.domain.catalog.models import ModePolicyPayload
from cys_core.domain.policy.defaults import DEFAULT_MODE_POLICY
from cys_core.domain.policy.pure import allow_tool_pure
from cys_core.domain.runs.models import InteractionMode

logger = structlog.get_logger(__name__)


def allow_tool_for_profile(
    mode: InteractionMode | None,
    tool_name: str,
    profile_id: str | None = None,
    *,
    mode_policy: ModePolicyPayload | None = None,
) -> bool:
    if mode_policy is not None:
        return allow_tool_pure(mode, tool_name, mode_policy=mode_policy)
    if profile_id:
        try:
            from cys_core.infrastructure.catalog.profile_policy import get_profile_policy

            return allow_tool_pure(mode, tool_name, mode_policy=get_profile_policy(profile_id).mode_policy)
        except Exception as exc:
            logger.warning(
                "profile_mode_policy_load_failed",
                profile_id=profile_id,
                tool_name=tool_name,
                error=str(exc),
            )
    return allow_tool_pure(mode, tool_name, mode_policy=DEFAULT_MODE_POLICY)
