from __future__ import annotations

import re

# General IB / advisory questions — skip multi-persona planner LLM.
_ADVISORY_PATTERNS = (
    re.compile(r"\bкак\s+защит", re.IGNORECASE),
    re.compile(r"\bhow\s+to\s+protect\b", re.IGNORECASE),
    re.compile(r"\bbest\s+practice", re.IGNORECASE),
    re.compile(r"\bрекомендац", re.IGNORECASE),
    re.compile(r"\badvisory\b", re.IGNORECASE),
    re.compile(r"\bконсультац", re.IGNORECASE),
    re.compile(r"\bactive\s+directory\b", re.IGNORECASE),
    re.compile(r"\bзащит\w*\s+active\s+directory\b", re.IGNORECASE),
)


def is_advisory_goal(goal: str) -> bool:
    """True when goal is general security advisory (consultant-only path)."""
    text = (goal or "").strip()
    if not text:
        return False
    return any(p.search(text) for p in _ADVISORY_PATTERNS)
