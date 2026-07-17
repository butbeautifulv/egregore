from __future__ import annotations

import pytest

from cys_core.integrations.siem_mcp_client import _siem_pdql_hint


@pytest.mark.unit
def test_siem_pdql_hint_for_search_events() -> None:
    hint = _siem_pdql_hint("search_events", "PDQL parse.error at token ':'")
    assert "investigate_incident" in hint
    assert "INC-123" in hint


@pytest.mark.unit
def test_siem_pdql_hint_skips_unrelated_tools() -> None:
    assert _siem_pdql_hint("investigate_incident", "PDQL parse.error") == ""
