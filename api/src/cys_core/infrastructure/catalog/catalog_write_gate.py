from __future__ import annotations

import hashlib
import threading
from typing import Callable

from cys_core.application.ports.catalog import AgentCatalogPort
from cys_core.application.ports.catalog_audit import CatalogAuditPort
from cys_core.application.ports.registry_catalogs import (
    McpServerCatalogPort,
    PlanCatalogPort,
    SkillCatalogPort,
)
from cys_core.domain.agents.control import is_control_persona
from cys_core.domain.catalog.models import (
    AgentCatalogEntry,
    McpServerEntry,
    PlanCatalogEntry,
    SkillCatalogEntry,
    StagingStatus,
)
from cys_core.domain.catalog.validation import CrossRefValidator
from cys_core.infrastructure.catalog.profile_policy import get_profile_policy
from cys_core.domain.security.exceptions import SecurityViolation
from cys_core.domain.security.factory import get_input_sanitizer
from cys_core.domain.security.sanitizer import InjectionVerdict
from cys_core.domain.security.system_prompt_assembler import (
    assemble_trusted_system_context,
    extract_persona_prompt,
    had_embedded_rule_sections,
    resolve_persona_prompt,
)


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

    def _normalize_agent_entry(self, entry: AgentCatalogEntry, *, actor: str) -> AgentCatalogEntry:
        sanitizer = get_input_sanitizer()
        raw = entry.persona_prompt or entry.system_prompt
        stripped_rules = False
        if raw:
            persona_candidate = extract_persona_prompt(raw)
            stripped_rules = had_embedded_rule_sections(raw)
            verdict = sanitizer.classify(persona_candidate)
            if verdict is InjectionVerdict.HARD:
                raise SecurityViolation("Prompt injection detected in catalog persona")
            persona = sanitizer.filter_patterns(persona_candidate)
            entry.persona_prompt = persona
        else:
            persona = resolve_persona_prompt(entry)
            entry.persona_prompt = persona

        ctx = assemble_trusted_system_context(persona, language=entry.language)
        entry.system_prompt = ""
        entry.system_prompt_digest = ctx.digest

        if stripped_rules:
            self._audit.record_change(
                "persona_rules_stripped",
                agent=entry.name,
                actor=actor,
                resource_type="agent",
                resource_id=entry.name,
            )
        return entry

    def upsert_agent(self, entry: AgentCatalogEntry, *, actor: str = "api") -> AgentCatalogEntry:
        if is_control_persona(entry.name):
            raise SecurityViolation(f"Control persona '{entry.name}' is immutable")
        entry = self._normalize_agent_entry(entry, actor=actor)
        validator = CrossRefValidator(
            known_skill_ids=self._skill_ids(),
            known_tool_names=self._tool_names(),
            policy_getter=get_profile_policy,
        )
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
        if is_control_persona(name):
            raise SecurityViolation(f"Control persona '{name}' is immutable")
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
