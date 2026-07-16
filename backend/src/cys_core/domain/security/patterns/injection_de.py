from __future__ import annotations

HARD_INJECTION_PATTERNS_DE = [
    r"ignorier\w*\s+(?:alle\s+)?(?:vorherigen?|früheren?)\s+anweisungen?",
    r"zeig\w*\s+(?:dein\w*\s+)?(?:system\s+)?prompt",
    r"du\s+bist\s+jetzt\s+im\s+entwicklermodus",
    r"umgeh\w*\s+(?:alle\s+)?sicherheit",
    r"wiederhol\w*\s+den\s+text\s+oben",
]

SOFT_INJECTION_PATTERNS_DE = [
    r"entwicklermodus",
    r"du\s+bist\s+jetzt\s+",
]
