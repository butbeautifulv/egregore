from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

from bootstrap.settings import get_settings
from cys_core.application.runtime_config import (
    get_jina_api_key,
    get_perplexity_api_key,
    get_serper_api_key,
    get_web_search_provider,
)
from cys_core.infrastructure.tools.adapters.search_stack import (
    enhance_query,
    jina_search,
    judge_search_relevance,
    perplexity_search,
)


def web_search(query: str, *, limit: int | None = None) -> dict[str, Any]:
    settings = get_settings()
    resolved_limit = limit if limit is not None else settings.web_search_default_limit
    meta = enhance_query(query)
    enhanced = meta["enhanced_query"]
    engines: list[str] = []
    if get_serper_api_key():
        engines.extend(["serper", "perplexity", "jina", "duckduckgo"])
    else:
        engines.append(get_web_search_provider().lower() or "duckduckgo")
        if get_perplexity_api_key():
            engines.insert(0, "perplexity")
        if get_jina_api_key():
            engines.insert(0, "jina")

    tried: list[dict[str, Any]] = []
    for engine in engines:
        if engine == "serper":
            result = _serper_search(enhanced, limit=resolved_limit)
        elif engine == "perplexity":
            result = perplexity_search(enhanced, limit=resolved_limit)
        elif engine == "jina":
            result = jina_search(enhanced, limit=resolved_limit)
        else:
            result = _duckduckgo_search(enhanced, limit=resolved_limit)
        tried.append(result)
        blob = json.dumps(result, ensure_ascii=False)
        if result.get("success") and judge_search_relevance(query, blob):
            result["query_meta"] = meta
            result["engine_used"] = engine
            return result
    best = next((r for r in tried if r.get("success")), tried[-1] if tried else {"success": False, "results": []})
    best["query_meta"] = meta
    best["judge_passed"] = False
    return best


def _duckduckgo_search(query: str, *, limit: int) -> dict[str, Any]:
    settings = get_settings()
    base = settings.duckduckgo_api_url.rstrip("/?")
    url = base + "/?" + urllib.parse.urlencode(
        {"q": query, "format": "json", "no_redirect": "1", "no_html": "1"}
    )
    try:
        with urllib.request.urlopen(url, timeout=settings.duckduckgo_api_timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {"success": False, "error": str(exc), "results": [], "provider": "duckduckgo"}
    results = []
    abstract = data.get("AbstractText") or data.get("Heading")
    if abstract:
        results.append({"title": data.get("Heading", ""), "snippet": abstract, "url": data.get("AbstractURL", "")})
    for topic in (data.get("RelatedTopics") or [])[:limit]:
        if isinstance(topic, dict) and "Text" in topic:
            results.append(
                {
                    "title": topic.get("Text", "")[:80],
                    "snippet": topic.get("Text", ""),
                    "url": topic.get("FirstURL", ""),
                }
            )
    return {"success": True, "provider": "duckduckgo", "results": results[:limit]}


def _serper_search(query: str, *, limit: int) -> dict[str, Any]:
    settings = get_settings()
    payload = json.dumps({"q": query, "num": limit}).encode("utf-8")
    req = urllib.request.Request(
        settings.serper_api_url,
        data=payload,
        headers={"X-API-KEY": get_serper_api_key(), "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=settings.serper_api_timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {"success": False, "error": str(exc), "results": [], "provider": "serper"}
    organic = data.get("organic", [])[:limit]
    results = [
        {"title": item.get("title", ""), "snippet": item.get("snippet", ""), "url": item.get("link", "")}
        for item in organic
    ]
    return {"success": True, "provider": "serper", "results": results}
