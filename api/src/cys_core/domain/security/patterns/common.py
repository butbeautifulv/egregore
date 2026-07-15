from __future__ import annotations

import re

# Language-agnostic delimiter / markup / special-token injection patterns.
HARD_COMMON_PATTERNS = [
    r"<\s*/?\s*system\s*>",
    r"\[INST\]",
    r"###\s*instruction",
]

SOFT_COMMON_PATTERNS = [
    r"<\s*img\s+[^>]+src\s*=",
]

BASE64_TOKEN = re.compile(r"(?:[A-Za-z0-9+/]{16,}={0,2})")
HEX_TOKEN = re.compile(r"\b[0-9a-fA-F]{32,}\b")
