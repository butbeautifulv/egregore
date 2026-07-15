from __future__ import annotations

from cys_core.domain.runs.models import ContextKind, RunContext


def checkpoint_key(ctx: RunContext, *, persona: str = "conductor") -> str:
    """LangGraph thread key from RunContext."""
    if ctx.kind in (ContextKind.SESSION, ContextKind.INVESTIGATION):
        return f"run:{ctx.kind.value}:{ctx.context_id}"
    if persona and ctx.kind == ContextKind.JOB:
        return f"worker:{persona}:{ctx.context_id}"
    return f"run:{ctx.kind.value}:{ctx.context_id}"
