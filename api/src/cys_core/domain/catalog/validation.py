from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cys_core.domain.catalog.models import AgentCatalogEntry, SkillCatalogEntry
from cys_core.domain.security.profile_tools import filter_tools_for_profile


class CatalogValidationError(ValueError):
    pass


class CrossRefValidator:
    """Validate catalog entries reference known tools/skills within profile policy."""

    def __init__(
        self,
        *,
        known_skill_ids: set[str] | None = None,
        known_tool_names: set[str] | None = None,
        policy_getter: Callable[[str], Any] | None = None,
    ) -> None:
        self._known_skill_ids = known_skill_ids
        self._known_tool_names = known_tool_names
        self._policy_getter = policy_getter

    def _profile_policy(self, profile_id: str):
        if self._policy_getter is None:
            return None
        try:
            return self._policy_getter(profile_id)
        except Exception:
            return None

    def validate_agent(self, entry: AgentCatalogEntry) -> None:
        if self._known_tool_names is not None:
            unknown_tools = [tool for tool in entry.tools if tool not in self._known_tool_names]
            if unknown_tools:
                raise CatalogValidationError(f"Unknown tools: {', '.join(unknown_tools)}")
        policy = self._profile_policy(entry.profile_id)
        allowed = filter_tools_for_profile(entry.tools, entry.profile_id, policy=policy)
        if len(allowed) != len(entry.tools):
            blocked = set(entry.tools) - set(allowed)
            raise CatalogValidationError(f"Tools blocked by profile policy: {', '.join(sorted(blocked))}")
        if entry.skills and self._known_skill_ids is not None:
            unknown_skills = [skill for skill in entry.skills if skill not in self._known_skill_ids]
            if unknown_skills:
                raise CatalogValidationError(f"Unknown skills: {', '.join(unknown_skills)}")

    def validate_skill(self, entry: SkillCatalogEntry) -> None:
        if not entry.id.strip():
            raise CatalogValidationError("Skill id is required")
        if entry.staging_status.value == "draft" and not entry.body.strip():
            raise CatalogValidationError("Draft skill requires non-empty body")
