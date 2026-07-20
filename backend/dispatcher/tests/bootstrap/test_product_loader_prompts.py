from __future__ import annotations

import pytest

from bootstrap.product_loader import _parse_prompt_md
from cys_core.application.observability.prompt_resolver import PromptResolver
from cys_core.domain.observability.models import PromptRef
from cys_core.infrastructure.observability.backends import NoopPromptBackend


@pytest.mark.unit
def test_product_loader_prompt_resolver_fallback(tmp_path):
    agent_dir = tmp_path / "soc"
    agent_dir.mkdir()
    (agent_dir / "AGENT.md").write_text("You are SOC analyst.", encoding="utf-8")
    resolver = PromptResolver(NoopPromptBackend())
    body = _parse_prompt_md(agent_dir / "AGENT.md")[1]
    resolved = resolver.resolve(PromptRef(name="soc"), fallback_text=body)
    assert resolved.text == "You are SOC analyst."
    assert resolved.source == "inline"
