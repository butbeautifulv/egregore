from __future__ import annotations

HARD_INJECTION_PATTERNS_EN = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?",
    r"disregard\s+(all\s+)?(previous|prior|system)\s+",
    r"reveal\s+(your\s+)?(system\s+)?prompt",
    r"you\s+are\s+now\s+(in\s+)?developer\s+mode",
    r"system\s+override",
    r"new\s+system\s+prompt",
    r"act\s+as\s+if\s+you(?:'re|\s+are)\s+not\s+bound",
    r"what\s+were\s+(your\s+)?(exact\s+)?instructions",
    r"repeat\s+the\s+text\s+above",
    r"output\s+(your\s+)?internal\s+data",
    r"bypass\s+(all\s+)?safety",
    r"do\s+anything\s+now",
    r"forget\s+(all\s+)?(previous|prior)\s+instructions?",
    r"print\s+(your\s+)?(system\s+)?prompt",
]

SOFT_INJECTION_PATTERNS_EN = [
    r"you\s+are\s+now\s+",
    r"developer\s+mode",
    r"override\s+(your\s+)?(security|safety)",
    r"thought:\s*i\s+should\s+ignore",
]
