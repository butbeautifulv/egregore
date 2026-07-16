from __future__ import annotations

import json
import os
from typing import Any

import httpx
import pytest

from cys_core.application.runs.tool_coercion import prepare_veil_tool_invocation

# Snapshot from veil ti_list_categories on k3s P30 (2026-07-09).
FIXTURE_CATEGORY_IDS = frozenset(
    {
        "vuln",
        "ti",
        "mitre",
        "detection",
        "playbook",
        "engage",
        "sbom",
        "code_rules",
        "dast",
        "lola",
    }
)

VEIL_MCP_TOOLS_IN_SCOPE = (
    "ti_search_in_category",
    "ti_list_categories",
    "playbook_search",
    "playbook_get",
    "playbook_procedure",
    "playbook_for_technique",
)

VEIL_REQUIRED_ARGS: dict[str, tuple[str, ...]] = {
    "ti_search_in_category": ("category", "query"),
    "ti_list_categories": (),
    "playbook_search": (),
    "playbook_get": ("id",),
    "playbook_procedure": ("id",),
    "playbook_for_technique": ("technique_id",),
}


def _mcp_call(url: str, tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments or {}},
    }
    response = httpx.post(
        url.rstrip("/"),
        json=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


def _live_veil_url() -> str | None:
    if os.environ.get("VEIL_MCP_LIVE", "").lower() not in ("1", "true", "yes"):
        return None
    url = os.environ.get("VEIL_MCP_URL", "").strip()
    if not url:
        return None
    return url


@pytest.mark.unit
def test_prepare_veil_ti_search_matches_fixture_categories() -> None:
    prepared = prepare_veil_tool_invocation("ti_search_in_category", {"query": "test", "category": "ti"})
    assert "arguments" in prepared
    assert prepared["arguments"]["category"] in FIXTURE_CATEGORY_IDS


@pytest.mark.unit
@pytest.mark.parametrize("tool_name,required", VEIL_REQUIRED_ARGS.items())
def test_veil_required_args_documented(tool_name: str, required: tuple[str, ...]) -> None:
    assert tool_name in VEIL_MCP_TOOLS_IN_SCOPE
    assert isinstance(required, tuple)


@pytest.mark.integration
def test_veil_live_categories_match_fixture() -> None:
    url = _live_veil_url()
    if url is None:
        pytest.skip("VEIL_MCP_URL not set")
    body = _mcp_call(url, "ti_list_categories")
    assert "error" not in body, body
    text_blocks = [
        block.get("text", "")
        for block in (body.get("result") or {}).get("content", [])
        if isinstance(block, dict)
    ]
    assert text_blocks, "ti_list_categories returned no text content"
    parsed = json.loads(text_blocks[0])
    live_ids = {item["id"] for item in parsed.get("categories", []) if isinstance(item, dict) and item.get("id")}
    assert live_ids, "no category ids in live response"
    assert live_ids <= FIXTURE_CATEGORY_IDS or FIXTURE_CATEGORY_IDS <= live_ids


@pytest.mark.integration
def test_veil_live_ti_search_smoke() -> None:
    url = _live_veil_url()
    if url is None:
        pytest.skip("VEIL_MCP_URL not set")
    prepared = prepare_veil_tool_invocation("ti_search_in_category", {"query": "test", "category": "ti", "limit": 3})
    assert "arguments" in prepared
    body = _mcp_call(url, "ti_search_in_category", prepared["arguments"])
    assert "error" not in body, body
