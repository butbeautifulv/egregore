from __future__ import annotations

import pytest

from cys_core.application.observability.prompt_resolver import PromptResolver
from cys_core.domain.observability.models import PromptRef
from cys_core.infrastructure.observability.backends import NoopPromptBackend


@pytest.mark.unit
def test_prompt_resolver_fallback():
    resolver = PromptResolver(NoopPromptBackend())
    resolved = resolver.resolve(PromptRef(name="soc"), fallback_text="hello")
    assert resolved.text == "hello"
    assert resolved.source == "inline"
