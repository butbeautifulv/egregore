#!/usr/bin/env python3
"""HTTP smoke for veil-mcp tools/call chain."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request


def post(url: str, tool: str, arguments: dict | None = None) -> dict:
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments or {}},
        }
    ).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def text_result(body: dict) -> str:
    blocks = (body.get("result") or {}).get("content", [])
    return "\n".join(block.get("text", "") for block in blocks if isinstance(block, dict))


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8091/mcp"
    health_url = url.replace("/mcp", "/health")

    with urllib.request.urlopen(health_url, timeout=10) as resp:
        health_body = json.loads(resp.read().decode())
    if health_body.get("ok") is not True:
        raise SystemExit(f"health check failed: {health_body}")

    health = post(url, "ti_health")
    health_json = json.loads(text_result(health))
    if health_json.get("neo4j_ok") is not True:
        raise SystemExit(f"ti_health neo4j not ok: {health_json}")

    cats = json.loads(text_result(post(url, "ti_list_categories")))
    cat_ids = [c["id"] for c in cats.get("categories", []) if isinstance(c, dict) and c.get("id")]
    if not cat_ids:
        raise SystemExit("ti_list_categories returned no ids")

    category = "ti" if "ti" in cat_ids else cat_ids[0]
    search = post(url, "ti_search_in_category", {"category": category, "query": "test", "limit": 3})
    search_json = json.loads(text_result(search))
    if "query" not in search_json:
        raise SystemExit(f"ti_search_in_category unexpected payload: {search_json}")

    pb = json.loads(text_result(post(url, "playbook_search", {"query": "phishing", "limit": 3})))
    items = pb.get("skills") or pb.get("results") or pb.get("playbooks") or pb.get("items") or []
    if not items and isinstance(pb, list):
        items = pb
    playbook_id = None
    for item in items:
        if isinstance(item, dict) and item.get("id"):
            playbook_id = item["id"]
            break
    if not playbook_id:
        raise SystemExit(f"playbook_search returned no id: {pb}")

    post(url, "playbook_get", {"id": playbook_id})
    post(url, "playbook_procedure", {"id": playbook_id})
    post(url, "playbook_for_technique", {"technique_id": "T1059.001"})
    print(f"veil-mcp smoke passed category={category} playbook_id={playbook_id}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.URLError as exc:
        print(f"veil-mcp smoke failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
