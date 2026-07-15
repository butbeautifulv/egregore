from __future__ import annotations

import hashlib

from cys_core.application.ports.observability.prompt_backend import PromptBackendPort
from cys_core.domain.observability.models import PromptRef, ResolvedPrompt


class LangfusePromptBackend:
    """Resolve prompts from Langfuse prompt management API."""

    def resolve(self, ref: PromptRef, *, fallback_text: str = "") -> ResolvedPrompt | None:
        try:
            from langfuse import get_client

            client = get_client()
            prompt = client.get_prompt(ref.name, label=ref.label, version=ref.version)
            text = prompt.compile() if hasattr(prompt, "compile") else str(prompt.prompt)
            digest = hashlib.sha256(text.encode()).hexdigest()[:16]
            return ResolvedPrompt(text=text, ref=ref, source="langfuse", digest=digest)
        except Exception:
            if fallback_text:
                return ResolvedPrompt(text=fallback_text, ref=ref, source="langfuse-fallback")
            return None
