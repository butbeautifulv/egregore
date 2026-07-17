from __future__ import annotations

from typing import Protocol

from cys_core.domain.observability.models import PromptRef, ResolvedPrompt


class PromptBackendPort(Protocol):
    def resolve(self, ref: PromptRef, *, fallback_text: str = "") -> ResolvedPrompt | None: ...
