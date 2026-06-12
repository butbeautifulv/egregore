from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

from bootstrap.settings import settings
from cys_core.domain.security.prompt_context import TrustedSystemContext, build_trusted_system_context

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RULES_SKIP = frozenset({"README.md"})


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

    def build_system_context(self, persona: str) -> TrustedSystemContext:
        return build_trusted_system_context(persona, self._rules_block)


@lru_cache
def get_product_context() -> ProductContext:
    return ProductContext()
