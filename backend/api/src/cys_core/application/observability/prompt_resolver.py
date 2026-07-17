from __future__ import annotations

import hashlib

from cys_core.application.ports.observability.prompt_backend import PromptBackendPort
from cys_core.domain.observability.models import PromptRef, ResolvedPrompt


class PromptResolver:
    """Compose prompt backends with filesystem fallback."""

    def __init__(self, *backends: PromptBackendPort) -> None:
        self._backends = backends

    def resolve(self, ref: PromptRef, *, fallback_text: str = "") -> ResolvedPrompt:
        for backend in self._backends:
            resolved = backend.resolve(ref, fallback_text=fallback_text)
            if resolved is not None and resolved.text:
                return resolved
        digest = hashlib.sha256(fallback_text.encode()).hexdigest()[:16] if fallback_text else ""
        return ResolvedPrompt(text=fallback_text, ref=ref, source="inline", digest=digest)
