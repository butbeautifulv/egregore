from __future__ import annotations

import pytest

from cys_core.application.workers.tool_result_cache import (
    clear_tool_result_cache,
    get_cached,
    normalize_playbook_query,
    set_cached,
)


@pytest.mark.unit
def test_tool_result_cache_roundtrip() -> None:
    clear_tool_result_cache("job-cache")
    assert get_cached("job-cache", "ti_list_categories") is None
    set_cached("job-cache", "ti_list_categories", '{"ok":true}')
    assert get_cached("job-cache", "ti_list_categories") == '{"ok":true}'
    clear_tool_result_cache("job-cache")
    assert get_cached("job-cache", "ti_list_categories") is None


@pytest.mark.unit
def test_normalize_playbook_query() -> None:
    assert normalize_playbook_query("  Phishing   Attack ") == "phishing attack"
