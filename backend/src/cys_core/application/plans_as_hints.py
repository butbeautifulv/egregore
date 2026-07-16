from __future__ import annotations

from pathlib import Path

import yaml

from cys_core.application.ports.agents_root import AgentsRootPort
from cys_core.application.ports.registry_catalogs import PlanCatalogPort
from cys_core.application.runtime_config import get_use_dynamic_catalog

_plan_catalog: PlanCatalogPort | None = None
_agents_root: AgentsRootPort | None = None


def configure_plan_hints(*, plan_catalog: PlanCatalogPort, agents_root: AgentsRootPort) -> None:
    global _plan_catalog, _agents_root
    _plan_catalog = plan_catalog
    _agents_root = agents_root


def load_plan_hints(plans_dir: Path | None = None) -> list[dict]:
    """Load routing plans as conductor context hints (catalog when dynamic)."""
    if get_use_dynamic_catalog() and _plan_catalog is not None:
        entries = _plan_catalog.load_active()
        if entries:
            return [{"plan_id": entry.id, "rules": entry.rules} for entry in entries]
    if _agents_root is None:
        raise RuntimeError("Plan hints not configured — wire via bootstrap Container")
    base = plans_dir or (_agents_root.agents_root() / "plans")
    hints: list[dict] = []
    if not base.is_dir():
        return hints
    for path in sorted(base.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        routing = data.get("routing", data)
        rules = routing.get("rules", []) if isinstance(routing, dict) else []
        hints.append({"plan_id": data.get("id", path.stem), "rules": rules})
    return hints
