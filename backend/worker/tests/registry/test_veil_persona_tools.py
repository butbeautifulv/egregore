from __future__ import annotations

import pytest
import yaml

from cys_core.integrations.veil_mcp_client import FALLBACK_VEIL_TOOL_NAMES
from cys_core.registry.product_context import default_agents_root

_VEIL_PERSONAS = (
    "cloud",
    "compliance",
    "consultant",
    "dfir",
    "hunter",
    "identity",
    "intel",
    "network",
    "purple",
    "research",
    "soc",
)

_VEIL_TOOL_PREFIXES = ("playbook_", "ti_", "enrich_ioc")


def _persona_yaml(name: str) -> dict:
    path = default_agents_root() / "personas" / name / "agent.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.mark.unit
@pytest.mark.parametrize("persona", _VEIL_PERSONAS)
def test_veil_persona_has_veil_knowledge_skill(persona: str) -> None:
    data = _persona_yaml(persona)
    assert "veil-knowledge" in data.get("skills", [])


@pytest.mark.unit
@pytest.mark.parametrize("persona", _VEIL_PERSONAS)
def test_veil_persona_has_veil_tools(persona: str) -> None:
    tools = _persona_yaml(persona).get("tools", [])
    assert any(
        t in FALLBACK_VEIL_TOOL_NAMES or t.startswith(_VEIL_TOOL_PREFIXES) for t in tools
    ), f"{persona} has no veil tools in agent.yaml"


@pytest.mark.unit
def test_consultant_has_full_veil_ladder_tools() -> None:
    tools = set(_persona_yaml("consultant").get("tools", []))
    required = {
        "ti_list_categories",
        "ti_list_kinds_in_category",
        "ti_search_in_category",
        "ti_get_node",
        "ti_neighbors",
        "enrich_ioc",
        "playbook_search",
    }
    assert required.issubset(tools)
    assert "ti_health" not in tools
    skill_path = default_agents_root() / "skills" / "veil-knowledge" / "SKILL.md"
    assert skill_path.is_file()
    text = skill_path.read_text(encoding="utf-8")
    assert "playbook_search" in text
    assert "ti_search_in_category" in text


@pytest.mark.unit
def test_soc_does_not_include_playbook_for_technique() -> None:
    tools = set(_persona_yaml("soc").get("tools", []))
    assert "playbook_for_technique" not in tools


@pytest.mark.unit
def test_intel_includes_playbook_for_technique() -> None:
    tools = set(_persona_yaml("intel").get("tools", []))
    assert "playbook_for_technique" in tools

