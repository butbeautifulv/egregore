from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

from bootstrap.settings import settings
from cys_core.application.ports.catalog import AgentCatalogPort
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.domain.security.prompt_context import TrustedSystemContext
from cys_core.domain.security.system_prompt_assembler import assemble_trusted_system_context

# Not Path(__file__)-relative: this module is physically duplicated into
# both backend/api and backend/worker (no shared package between them, see
# docs/MICROSERVICES_SPLIT_PLAN.md §18) at different nesting depths —
# `Path(__file__).resolve().parents[N]` broke once this stopped being one
# level below whichever service was actually running.
# `uv run egregore ...` always invokes with CWD set to that service's own
# directory (where its `agents/` lives), so CWD is what "this service's
# own root" actually means now — same fix as bootstrap/settings.py's
# _settings_env_files().
PROJECT_ROOT = Path.cwd()
RULES_SKIP = frozenset({"README.md"})

_catalog_provider: AgentCatalogPort | None = None


def set_catalog_provider(catalog: AgentCatalogPort | None) -> None:
    global _catalog_provider
    _catalog_provider = catalog


def _default_catalog() -> AgentCatalogPort | None:
    if _catalog_provider is not None:
        return _catalog_provider
    # api's and worker's own wire_catalog_ports() calls set_catalog_provider()
    # explicitly at bootstrap (same pattern as discovery_tools.py) — reaching
    # for bootstrap.container here would be a layering violation: this is a
    # lower-level registry module, the composition root is above it. If no
    # provider was set (e.g. this code path reached before bootstrap ran),
    # fall back to the generic catalog_registry.
    try:
        from cys_core.infrastructure.catalog.catalog_registry import get_agent_catalog

        return get_agent_catalog()
    except Exception:
        return None


def default_agents_root() -> Path:
    root = Path(settings.agents_root)
    return root if root.is_absolute() else PROJECT_ROOT / root


class ProductManifest(BaseModel):
    name: str = "cys-agi"
    version: str = "0.1.0"
    description: str = ""
    default_plan: str = "full-assessment"


class ProductContext:
    """Loads shared product assets from agents/ (rules, plans, skills paths)."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or default_agents_root()
        self.personas_dir = self.root / "personas"
        self.rules_dir = self.root / "rules"
        self.plans_dir = self.root / "plans"
        self.skills_dir = self.root / "skills"
        self._manifest = self._load_manifest()
        self._rules_block = self._load_rules()

    def _load_manifest(self) -> ProductManifest:
        path = self.root / "manifest.yaml"
        if not path.exists():
            return ProductManifest()
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return ProductManifest.model_validate(
            {
                "name": data.get("name", "cys-agi"),
                "version": data.get("version", "0.1.0"),
                "description": data.get("description", ""),
                "default_plan": data.get("default_plan", "full-assessment"),
            }
        )

    def _load_rules(self) -> str:
        if not self.rules_dir.is_dir():
            return ""
        sections: list[str] = []
        for path in sorted(self.rules_dir.glob("*.md")):
            if path.name in RULES_SKIP:
                continue
            sections.append(path.read_text(encoding="utf-8").strip())
        if not sections:
            return ""
        return "## Global rules\n\n" + "\n\n".join(sections)

    @property
    def manifest(self) -> ProductManifest:
        return self._manifest

    @property
    def rules_block(self) -> str:
        return self._rules_block

    @property
    def skills_path(self) -> str:
        try:
            return str(self.skills_dir.relative_to(PROJECT_ROOT))
        except ValueError:
            return str(self.skills_dir)

    def augment_prompt(self, base_prompt: str) -> str:
        return self.build_system_context(base_prompt).text

    def build_system_context(self, persona: str, *, profile_id: str = DEFAULT_PROFILE_ID) -> TrustedSystemContext:
        _ = profile_id
        return assemble_trusted_system_context(persona, language="ru")


@lru_cache
def get_product_context() -> ProductContext:
    return ProductContext()
