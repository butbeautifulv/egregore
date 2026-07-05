from __future__ import annotations

from pathlib import Path

import yaml

from bootstrap.settings import get_settings
from cys_core.domain.catalog.models import (
    CatalogSource,
    McpServerEntry,
    PlanCatalogEntry,
    StagingStatus,
    SkillCatalogEntry,
)
from cys_core.application.plans.plan_loader import load_plan_routing
from cys_core.registry.product_context import default_agents_root
from cys_core.registry.skill_registry import SkillRegistry, compute_skill_hash, _parse_skill_md


def load_skills_for_seed(profile_id: str = "cybersec-soc") -> list[SkillCatalogEntry]:
    entries: list[SkillCatalogEntry] = []
    reg = SkillRegistry.load()
    for manifest in reg.all():
        body = ""
        if manifest.path:
            path = Path(manifest.path)
            if path.exists():
                _, body = _parse_skill_md(path)
        entries.append(
            SkillCatalogEntry(
                id=manifest.skill_id,
                profile_id=profile_id,
                name=manifest.name,
                description=manifest.description,
                body=body,
                content_hash=manifest.content_hash or compute_skill_hash(body),
                trust_tier=manifest.trust_tier.value,
                staging_status=StagingStatus.BUILTIN,
                source=CatalogSource.SEED,
            )
        )
    return entries


def load_plans_for_seed(profile_id: str = "cybersec-soc") -> list[PlanCatalogEntry]:
    plans_dir = default_agents_root() / "plans"
    entries: list[PlanCatalogEntry] = []
    if not plans_dir.is_dir():
        return entries
    for path in sorted(plans_dir.glob("*.yaml")):
        routing = load_plan_routing(path)
        rules = [rule.model_dump() for rule in routing.rules]
        entries.append(
            PlanCatalogEntry(
                id=routing.id,
                profile_id=profile_id,
                name=routing.name,
                description=routing.description,
                rules=rules,
                active=True,
                source=CatalogSource.SEED,
            )
        )
    return entries


def load_mcp_servers_for_seed(profile_id: str = "cybersec-soc") -> list[McpServerEntry]:
    from cys_core.integrations.veil_mcp_client import FALLBACK_VEIL_TOOL_NAMES

    settings = get_settings()
    servers: list[McpServerEntry] = []
    if settings.veil_mcp_enabled and settings.veil_mcp_url:
        servers.append(
            McpServerEntry(
                id="veil",
                url=settings.veil_mcp_url,
                trust_tier="internal",
                profile_id=profile_id,
                health_status="unknown",
                allowed_tools=sorted(FALLBACK_VEIL_TOOL_NAMES),
            )
        )
    if settings.veneno_mcp_enabled and settings.veneno_mcp_url:
        servers.append(
            McpServerEntry(
                id="veneno",
                url=settings.veneno_mcp_url,
                trust_tier="privileged",
                profile_id=profile_id,
                health_status="unknown",
            )
        )
    return servers
