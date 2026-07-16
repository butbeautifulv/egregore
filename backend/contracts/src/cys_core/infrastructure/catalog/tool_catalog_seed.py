from __future__ import annotations

from cys_core.application.tools.providers import ALL_PROVIDER_DEFINITIONS
from cys_core.domain.catalog.models import CatalogSource, ToolCatalogEntry
from cys_core.domain.security.risk import ACTION_RISK_MAPPING

_HANDLER_BY_MODULE: dict[str, str] = {
    "builtin": "builtin",
    "discovery": "builtin",
    "orchestration": "builtin",
    "rag": "rag",
    "sandbox": "sandbox",
    "siem": "siem",
    "siem-mcp": "siem_mcp",
    "veil-mcp": "veil",
    "web": "web",
}


def load_tools_for_seed(profile_id: str = "cybersec-soc") -> list[ToolCatalogEntry]:
    entries: list[ToolCatalogEntry] = []
    seen: set[str] = set()
    for defn in ALL_PROVIDER_DEFINITIONS:
        if defn.name in seen:
            continue
        seen.add(defn.name)
        risk = ACTION_RISK_MAPPING.get(defn.name)
        entries.append(
            ToolCatalogEntry(
                id=defn.name,
                profile_id=profile_id,
                name=defn.name,
                description=defn.description,
                risk_tier=risk or "medium",
                handler=_HANDLER_BY_MODULE.get(defn.module, defn.module),
                source=CatalogSource.SEED,
            )
        )
    return entries
