from __future__ import annotations

import threading

_lock = threading.Lock()
_cache: dict[str, dict[str, str]] = {}


def get_cached(job_id: str, key: str) -> str | None:
    if not job_id or not key:
        return None
    with _lock:
        return _cache.get(job_id, {}).get(key)


def set_cached(job_id: str, key: str, value: str) -> None:
    if not job_id or not key or not value:
        return
    with _lock:
        _cache.setdefault(job_id, {})[key] = value


def clear_tool_result_cache(job_id: str) -> None:
    if job_id:
        with _lock:
            _cache.pop(job_id, None)


def normalize_playbook_query(query: str) -> str:
    return " ".join(query.strip().lower().split())
