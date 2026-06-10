from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

from cys_core.registry.models import AgentConfig, AgentDefinition
from cys_core.registry.product_context import ProductContext, default_agents_root

PROMPT_FILENAMES = ("AGENT.md", "SKILL.md")
PERSONAS_DIRNAME = "personas"

LANGUAGE_SUFFIX = (
    "\n\nLanguage: You may think in English, but you MUST answer in Russian. "
    "Keep JSON field names in English; values should be in Russian."
)


def _iter_persona_dirs(base: Path):
    personas = base / PERSONAS_DIRNAME
    if not personas.is_dir():
        return
    for agent_dir in sorted(personas.iterdir()):
        if agent_dir.is_dir() and not agent_dir.name.startswith("."):
            yield agent_dir


def _resolve_prompt_path(agent_dir: Path) -> Path | None:
    for name in PROMPT_FILENAMES:
        path = agent_dir / name
        if path.exists():
            return path
    return None


def _parse_prompt_md(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
        if match:
            frontmatter = yaml.safe_load(match.group(1)) or {}
            body = match.group(2).strip()
            return frontmatter, body
    return {}, text.strip()


class AgentRegistry:
    def __init__(self, agents: dict[str, AgentDefinition]) -> None:
        self._agents = agents

    @classmethod
    def load(cls, root: Path | None = None) -> AgentRegistry:
        base = root or default_agents_root()
        product = ProductContext(base)
        agents: dict[str, AgentDefinition] = {}
        for agent_dir in _iter_persona_dirs(base):
            yaml_path = agent_dir / "agent.yaml"
            prompt_path = _resolve_prompt_path(agent_dir)
            if not yaml_path.exists() or prompt_path is None:
                continue
            config = AgentConfig.model_validate(yaml.safe_load(yaml_path.read_text(encoding="utf-8")))
            _, body = _parse_prompt_md(prompt_path)
            sample_path = agent_dir / config.sample
            sample_input = sample_path.read_text(encoding="utf-8").strip() if sample_path.exists() else None
            system_prompt = body
            if config.language == "ru":
                system_prompt = f"{body}{LANGUAGE_SUFFIX}"
            system_prompt = product.augment_prompt(system_prompt)
            agents[config.name] = AgentDefinition(
                name=config.name,
                description=config.description,
                role=config.role,
                system_prompt=system_prompt,
                schema_name=config.output_schema,
                tools=config.tools,
                hitl_tools=config.hitl_tools,
                trust_level=config.trust_level,
                bus_recipients=config.bus_recipients,
                sample_input=sample_input,
                interrupt_on=config.interrupt_on,
                skill_path=agent_dir,
            )
        return cls(agents)

    def get(self, name: str) -> AgentDefinition:
        if name not in self._agents:
            raise KeyError(f"Unknown agent: {name}")
        return self._agents[name]

    def all(self) -> list[AgentDefinition]:
        return list(self._agents.values())

    def names(self) -> list[str]:
        return list(self._agents.keys())

    def by_role(self, role: str) -> list[AgentDefinition]:
        return [a for a in self._agents.values() if a.role == role]


@lru_cache
def get_agent_registry() -> AgentRegistry:
    return AgentRegistry.load()
