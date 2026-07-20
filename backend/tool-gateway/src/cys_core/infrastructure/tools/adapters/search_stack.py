from __future__ import annotations

import json
import random
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

_RETRYABLE_HTTP_CODES = frozenset({408, 409, 429, 500, 502, 503, 504})


def _is_transient_urllib_error(exc: Exception) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in _RETRYABLE_HTTP_CODES
    if isinstance(exc, urllib.error.URLError | socket.timeout | TimeoutError):
        return True
    return False


def _urlopen_with_retry(fn: Callable[[], T], *, max_retries: int, source: str) -> T:
    """Retry a urlopen-based call on transient network/HTTP failures, mirroring
    cys_core.integrations.mcp_http.call_with_retry's backoff — perplexity/jina use
    urllib rather than httpx so can't share that helper directly."""
    import structlog

    logger = structlog.get_logger(__name__)
    attempt = 0
    while True:
        try:
            return fn()
        except Exception as exc:
            if attempt >= max_retries or not _is_transient_urllib_error(exc):
                raise
            delay = min(8.0, 0.25 * (2**attempt)) * (1.0 + random.random())
            logger.warning(
                "search_call_retrying",
                source=source,
                attempt=attempt + 1,
                max_retries=max_retries,
                delay_s=round(delay, 2),
                error=str(exc),
            )
            time.sleep(delay)
            attempt += 1


def enhance_query(query: str) -> dict[str, str]:
    text = query.strip()
    lower = text.lower()
    multi_step_words = ("compare", "analyze", "why", "how many", "list all")
    query_type = "multi-step" if any(w in lower for w in multi_step_words) else "factual"
    academic_words = ("paper", "research", "arxiv", "study", "theorem")
    query_topic = "academic" if any(w in lower for w in academic_words) else "general"
    enhanced = text
    if len(text.split()) <= 3 and "?" not in text:
        enhanced = f"What is {text}?"
    return {
        "enhanced_query": enhanced,
        "query_type": query_type,
        "query_topic": query_topic,
    }


def judge_search_relevance(query: str, results_text: str) -> bool:
    llm = _judge_search_relevance_llm(query, results_text)
    if llm is not None:
        return llm
    if not results_text.strip():
        return False
    lower = results_text.lower()
    if "error" in lower and len(lower) < 80:
        return False
    tokens = [t for t in re.split(r"\W+", query.lower()) if len(t) > 3]
    if not tokens:
        return bool(results_text.strip())
    hits = sum(1 for token in tokens if token in lower)
    return hits >= max(1, len(tokens) // 3)


def _judge_search_relevance_llm(query: str, results_text: str) -> bool | None:
    try:
        from bootstrap.settings import get_settings
        from cys_core.application.runtime_config import get_search_judge_llm
        from cys_core.domain.workers.job_budget import JobBudgetTracker

        # cys_core.llm isn't part of this package (no agent-execution
        # frameworks, see docs/MSP_BACKLOG.md §21.5) — always
        # falls through to the except below (skip LLM-based judging).
        # Deliberate, not stale — see multimodal.py's vision_analyze for the
        # same pattern/reasoning.
        from cys_core.llm.reasoning import get_reasoning_model_connector  # ty: ignore[unresolved-import]

        settings = get_settings()
        if not get_search_judge_llm() or not settings.reasoning_model.strip():
            return None
        JobBudgetTracker.record_tokens(
            "judge:search",
            JobBudgetTracker.estimate_tokens(results_text[: settings.search_judge_input_max]),
        )
        model = get_reasoning_model_connector().create_model()
        prompt = (
            f"Query: {query}\nResults:\n{results_text[: settings.search_judge_prompt_max]}\n"
            "Did the results answer the query? Reply YES or NO only."
        )
        response = model.invoke(prompt)
        text = str(getattr(response, "content", response)).strip().upper()
        if text.startswith("YES"):
            return True
        if text.startswith("NO"):
            return False
        return None
    except Exception:
        return None


def perplexity_search(query: str, *, limit: int | None = None) -> dict:
    from bootstrap.settings import get_settings
    from cys_core.application.runtime_config import get_perplexity_api_key

    settings = get_settings()
    key = get_perplexity_api_key()
    if not key:
        return {"success": False, "error": "PERPLEXITY_API_KEY not set", "results": []}
    body = json.dumps({"model": "sonar", "messages": [{"role": "user", "content": query}]}).encode("utf-8")
    req = urllib.request.Request(
        settings.perplexity_api_url,
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )

    def _call() -> dict:
        with urllib.request.urlopen(req, timeout=settings.perplexity_api_timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8"))

    try:
        from cys_core.application.runtime_config import get_mcp_call_max_retries

        data = _urlopen_with_retry(_call, max_retries=get_mcp_call_max_retries(), source="perplexity-search")
    except Exception as exc:
        return {"success": False, "error": str(exc), "results": []}
    content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
    return {"success": bool(content), "results": [{"snippet": content}], "provider": "perplexity"}


def jina_search(query: str, *, limit: int | None = None) -> dict:
    from bootstrap.settings import get_settings
    from cys_core.application.runtime_config import get_jina_api_key

    settings = get_settings()
    del limit  # Jina returns a single synthesized snippet; limit kept for API symmetry.
    key = get_jina_api_key()
    if not key:
        return {"success": False, "error": "JINA_API_KEY not set", "results": []}
    base = settings.jina_search_api_url.rstrip("/?")
    url = base + "/?" + urllib.parse.urlencode({"q": query})
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})

    def _call() -> str:
        with urllib.request.urlopen(req, timeout=settings.jina_search_api_timeout_s) as resp:
            return resp.read().decode("utf-8")

    try:
        from cys_core.application.runtime_config import get_mcp_call_max_retries

        text = _urlopen_with_retry(_call, max_retries=get_mcp_call_max_retries(), source="jina-search")
    except Exception as exc:
        return {"success": False, "error": str(exc), "results": []}
    return {
        "success": bool(text.strip()),
        "results": [{"snippet": text[: settings.jina_search_snippet_max]}],
        "provider": "jina",
    }
