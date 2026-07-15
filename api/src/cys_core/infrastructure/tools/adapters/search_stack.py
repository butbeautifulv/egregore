from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request


def enhance_query(query: str) -> dict[str, str]:
    text = query.strip()
    lower = text.lower()
    query_type = "multi-step" if any(w in lower for w in ("compare", "analyze", "why", "how many", "list all")) else "factual"
    query_topic = "academic" if any(w in lower for w in ("paper", "research", "arxiv", "study", "theorem")) else "general"
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
        from cys_core.llm.reasoning import get_reasoning_model_connector

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
    resolved_limit = limit if limit is not None else settings.perplexity_search_default_limit
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
    try:
        with urllib.request.urlopen(req, timeout=settings.perplexity_api_timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
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
    try:
        with urllib.request.urlopen(req, timeout=settings.jina_search_api_timeout_s) as resp:
            text = resp.read().decode("utf-8")
    except Exception as exc:
        return {"success": False, "error": str(exc), "results": []}
    return {
        "success": bool(text.strip()),
        "results": [{"snippet": text[: settings.jina_search_snippet_max]}],
        "provider": "jina",
    }
