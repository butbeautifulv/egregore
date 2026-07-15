from __future__ import annotations

import hashlib
from pathlib import Path

from cys_core.application.ports.observability.prompt_backend import PromptBackendPort
from cys_core.domain.observability.models import PromptRef, ResolvedPrompt


class FilesystemPromptBackend:
    """Resolve prompts from agent AGENT.md paths."""

    def __init__(self, agents_root: Path | None = None) -> None:
        from cys_core.registry.product_context import default_agents_root

        self.agents_root = agents_root or default_agents_root()

    def resolve(self, ref: PromptRef, *, fallback_text: str = "") -> ResolvedPrompt | None:
        for subdir in ("personas", "planner"):
            path = self.agents_root / subdir / ref.name / "AGENT.md"
            if path.is_file():
                text = path.read_text(encoding="utf-8")
                if text.startswith("---"):
                    parts = text.split("---", 2)
                    body = parts[2].strip() if len(parts) >= 3 else text
                else:
                    body = text.strip()
                digest = hashlib.sha256(body.encode()).hexdigest()[:16]
                return ResolvedPrompt(text=body, ref=ref, source="filesystem", digest=digest)
        if fallback_text:
            return ResolvedPrompt(text=fallback_text, ref=ref, source="filesystem-fallback")
        return None
