from __future__ import annotations

import pytest

from cys_core.infrastructure.tools.adapters.catalog_search import search_personas, search_skills, search_tools


@pytest.mark.unit
def test_search_personas_returns_results_key():
    result = search_personas("soc")
    assert "results" in result
    assert isinstance(result["results"], list)


@pytest.mark.unit
def test_search_skills_returns_results_key():
    result = search_skills("triage")
    assert "results" in result
    assert isinstance(result["results"], list)


@pytest.mark.unit
def test_search_tools_returns_results_key():
    result = search_tools("dedup", mode="agent")
    assert "results" in result
    assert isinstance(result["results"], list)
