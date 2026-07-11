from __future__ import annotations

import hashlib
import threading
from typing import Callable, cast

from cys_core.application.ports.catalog import AgentCatalogPort
from cys_core.application.ports.catalog_audit import CatalogAuditPort
from cys_core.application.ports.registry_catalogs import (
    McpServerCatalogPort,
    PlanCatalogPort,
    SkillCatalogPort,
)
from cys_core.domain.catalog.models import (
    AgentCatalogEntry,
    CatalogSource,
    McpServerEntry,
    PlanCatalogEntry,
    SkillCatalogEntry,
    StagingStatus,
)
from cys_core.domain.catalog.validation import CrossRefValidator
from cys_core.domain.security.factory import get_input_sanitizer


class CatalogWriteGate:
    def __init__(
        self,
        *,
        agent_catalog: AgentCatalogPort,
        skill_catalog: SkillCatalogPort,
        plan_catalog: PlanCatalogPort,
        mcp_catalog: McpServerCatalogPort,
        audit: CatalogAuditPort,
        validator: CrossRefValidator | None = None,
        reload: Callable[[], None] | None = None,
    ) -> None:
        self._agents = agent_catalog
        self._skills = skill_catalog
        self._plans = plan_catalog
        self._mcp = mcp_catalog
        self._audit = audit
        self._validator = validator or CrossRefValidator()
        self._reload = reload or (lambda: None)
        self._lock = threading.Lock()

    def _skill_ids(self) -> set[str]:
        return {entry.id for entry in self._skills.list_skills(enabled_only=False)}

    def _tool_names(self) -> set[str]:
        from cys_core.registry.tools import tool_registry

        return set(tool_registry.names())

    def upsert_agent(self, entry: AgentCatalogEntry, *, actor: str = "api") -> AgentCatalogEntry:
        sanitizer = get_input_sanitizer()
        if entry.system_prompt:
            entry.system_prompt = sanitizer.sanitize(entry.system_prompt, source="catalog")
            entry.system_prompt_digest = hashlib.sha256(entry.system_prompt.encode("utf-8")).hexdigest()[:16]
        validator = CrossRefValidator(known_skill_ids=self._skill_ids(), known_tool_names=self._tool_names())
        validator.validate_agent(entry)
        with self._lock:
            saved = self._agents.upsert_agent(entry)
            self._audit.record_change(
                "upsert",
                agent=entry.name,
                actor=actor,
                details={"version": saved.version},
                resource_type="agent",
                resource_id=entry.name,
            )
        self._reload()
        return saved

    def upsert_skill(self, entry: SkillCatalogEntry, *, actor: str = "api") -> SkillCatalogEntry:
        sanitizer = get_input_sanitizer()
        if entry.body:
            entry.body = sanitizer.sanitize(entry.body, source="skill")
            entry.content_hash = hashlib.sha256(entry.body.encode("utf-8")).hexdigest()
        self._validator.validate_skill(entry)
        with self._lock:
            saved = self._skills.upsert_skill(entry)
            self._audit.record_change(
                "upsert",
                agent=entry.id,
                actor=actor,
                details={"version": saved.version, "staging": saved.staging_status.value},
                resource_type="skill",
                resource_id=entry.id,
            )
        self._reload()
        return saved

    def approve_skill(
        self, skill_id: str, *, profile_id: str = "cybersec-soc", actor: str = "api"
    ) -> SkillCatalogEntry:
        entry = self._skills.get_skill(skill_id, profile_id=profile_id)
        if entry is None:
            raise KeyError(f"Unknown skill: {skill_id}")
        entry.staging_status = StagingStatus.VETTED
        return self.upsert_skill(entry, actor=actor)

    def upsert_plan(self, entry: PlanCatalogEntry, *, actor: str = "api") -> PlanCatalogEntry:
        with self._lock:
            saved = self._plans.upsert_plan(entry)
            self._audit.record_change(
                "upsert",
                agent=entry.id,
                actor=actor,
                details={"version": saved.version},
                resource_type="plan",
                resource_id=entry.id,
            )
        self._reload()
        return saved

    def upsert_mcp_server(self, entry: McpServerEntry, *, actor: str = "api") -> McpServerEntry:
        with self._lock:
            saved = self._mcp.upsert_server(entry)
            self._audit.record_change(
                "upsert",
                agent=entry.id,
                actor=actor,
                details={"url": entry.url},
                resource_type="mcp_server",
                resource_id=entry.id,
            )
        self._reload()
        return saved

    def delete_agent(self, name: str, *, profile_id: str = "cybersec-soc", actor: str = "api") -> bool:
        with self._lock:
            ok = self._agents.delete_agent(name, profile_id=profile_id)
            if ok:
                self._audit.record_change(
                    "delete",
                    agent=name,
                    actor=actor,
                    resource_type="agent",
                    resource_id=name,
                )
        self._reload()
        return ok

    def delete_skill(self, skill_id: str, *, profile_id: str = "cybersec-soc", actor: str = "api") -> bool:
        with self._lock:
            ok = self._skills.delete_skill(skill_id, profile_id=profile_id)
            if ok:
                self._audit.record_change(
                    "delete",
                    agent=skill_id,
                    actor=actor,
                    resource_type="skill",
                    resource_id=skill_id,
                )
        self._reload()
        return ok
