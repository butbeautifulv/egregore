"""Load product personas from agents/ into domain AgentDefinition objects."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from cys_core.domain.agents.models import AgentConfig, AgentDefinition
from cys_core.domain.security.system_prompt_assembler import assemble_trusted_system_context
from cys_core.registry.product_context import ProductContext, default_agents_root

PROMPT_FILENAMES = ("AGENT.md", "SKILL.md")
PERSONAS_DIRNAME = "personas"


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


def _load_agent_from_dir(agent_dir: Path, product: ProductContext) -> AgentDefinition | None:
    yaml_path = agent_dir / "agent.yaml"
    prompt_path = _resolve_prompt_path(agent_dir)
    if not yaml_path.exists() or prompt_path is None:
        return None
    config = AgentConfig.model_validate(yaml.safe_load(yaml_path.read_text(encoding="utf-8")))
    _, body = _parse_prompt_md(prompt_path)
    sample_path = agent_dir / config.sample
    sample_input = sample_path.read_text(encoding="utf-8").strip() if sample_path.exists() else None
    from bootstrap.observability_factory import build_prompt_backend
    from bootstrap.settings import get_settings
    from cys_core.application.observability.prompt_resolver import PromptResolver
    from cys_core.domain.observability.models import PromptRef

    # Built directly rather than via bootstrap.container.get_container(): that
    # composition root only exists in api/worker, not here in contracts,
    # while a PromptResolver only ever needs the (contracts-level) prompt
    # backend + settings — see ObservabilityContainer.get_prompt_resolver(),
    # which does the same construction for api/worker's own containers.
    resolver = PromptResolver(build_prompt_backend(get_settings().obs_prompt_backend))
    resolved = resolver.resolve(
        PromptRef(name=config.name),
        fallback_text=body,
    )
    persona_text = resolved.text if resolved else body
    system_ctx = assemble_trusted_system_context(persona_text, language=config.language)
    return AgentDefinition(
        name=config.name,
        description=config.description,
        role=config.role,
        system_prompt=system_ctx.text,
        system_prompt_digest=system_ctx.digest,
        persona_prompt=persona_text,
        language=config.language,
        schema_name=config.output_schema,
        tools=config.tools,
        skills=config.skills,
        hitl_tools=config.hitl_tools,
        trust_level=config.trust_level,
        bus_recipients=config.bus_recipients,
        sample_input=sample_input,
        interrupt_on=config.interrupt_on,
        skill_path=agent_dir,
        capabilities=config.capabilities,
        reasoning_mode=config.reasoning_mode,
    )


def load_agent_definitions(root: Path | None = None) -> dict[str, AgentDefinition]:
    """Read personas under agents/personas/ and control agents under agents/planner/."""
    base = root or default_agents_root()
    product = ProductContext(base)
    agents: dict[str, AgentDefinition] = {}
    agent_dirs = list(_iter_persona_dirs(base))
    planner_dir = base / "planner"
    if planner_dir.is_dir():
        agent_dirs.append(planner_dir)
    for agent_dir in agent_dirs:
        definition = _load_agent_from_dir(agent_dir, product)
        if definition is not None:
            agents[definition.name] = definition
    return agents
