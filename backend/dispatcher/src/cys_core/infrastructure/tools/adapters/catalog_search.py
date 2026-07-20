from __future__ import annotations

from typing import Any


def search_personas(query: str) -> dict[str, Any]:
    from cys_core.registry.discovery_tools import search_personas as _search

    return {"results": _search(query)}


def search_skills(query: str) -> dict[str, Any]:
    from cys_core.registry.discovery_tools import search_skills as _search

    return {"results": _search(query)}


def search_tools(query: str, mode: str = "agent") -> dict[str, Any]:
    from cys_core.domain.runs.models import InteractionMode
    from cys_core.registry.discovery_tools import search_tools as _search

    try:
        interaction_mode = InteractionMode(mode)
    except ValueError:
        interaction_mode = InteractionMode.AGENT
    return {"results": _search(query, mode=interaction_mode)}
