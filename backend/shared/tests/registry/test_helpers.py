from __future__ import annotations

import pytest

from bootstrap import product_loader
from bootstrap.agent_definitions_loader import get_default_agent_definitions_loader
from cys_core.registry import agents
from cys_core.registry.agents import configure_agent_definitions_loader


@pytest.mark.unit
def test_registry_helpers_and_temp_agent_loading(tmp_path, monkeypatch):
    assert list(product_loader._iter_persona_dirs(tmp_path)) == []

    empty_agent_dir = tmp_path / "empty"
    empty_agent_dir.mkdir()
    assert product_loader._resolve_prompt_path(empty_agent_dir) is None

    prompt = tmp_path / "prompt.md"
    prompt.write_text("---\ntitle: Test\n---\nBody text\n", encoding="utf-8")
    frontmatter, body = product_loader._parse_prompt_md(prompt)
    assert frontmatter == {"title": "Test"}
    assert body == "Body text"

    plain = tmp_path / "plain.md"
    plain.write_text("Plain body\n", encoding="utf-8")
    assert product_loader._parse_prompt_md(plain) == ({}, "Plain body")

    root = tmp_path / "agents-root"
    valid_dir = root / "personas" / "alpha"
    invalid_dir = root / "personas" / "skip-me"
    samples_dir = valid_dir / "samples"
    samples_dir.mkdir(parents=True)
    invalid_dir.mkdir(parents=True)
    (valid_dir / "agent.yaml").write_text(
        "\n".join(
            [
                "name: alpha",
                "description: Alpha agent",
                "role: specialist",
                "output_schema: RedTeamFinding",
                "tools: [read_repo_metadata]",
                "hitl_tools: {}",
                "trust_level: internal",
                "bus_recipients: [critic]",
                "language: en",
                "sample: samples/default.txt",
            ]
        ),
        encoding="utf-8",
    )
    (valid_dir / "AGENT.md").write_text("Alpha prompt", encoding="utf-8")
    (samples_dir / "default.txt").write_text("Sample input", encoding="utf-8")

    registry = agents.AgentRegistry.load(root)
    assert registry.names() == ["alpha"]
    assert registry.all()[0].sample_input == "Sample input"
    assert registry.by_role("specialist")[0].name == "alpha"
    with pytest.raises(KeyError, match="Unknown agent"):
        registry.get("missing")

    agents.get_agent_registry.cache_clear()

    monkeypatch.setattr("cys_core.registry.agents.get_use_dynamic_catalog", lambda: False)
    configure_agent_definitions_loader(get_default_agent_definitions_loader())
    monkeypatch.setattr(product_loader, "default_agents_root", lambda: root)
    try:
        assert agents.get_agent_registry().names() == ["alpha"]
    finally:
        agents.get_agent_registry.cache_clear()
