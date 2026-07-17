from __future__ import annotations

HARD_INJECTION_PATTERNS_ES = [
    r"ignor\w*\s+(?:todas?\s+)?(?:las\s+)?(?:instrucciones?\s+)?(?:anteriores?|previas?)",
    r"revela?\s+(?:tu\s+)?(?:prompt|instrucciones?)\s+(?:del\s+)?sistema",
    r"ahora\s+est[aá]s?\s+en\s+modo\s+desarrollador",
    r"anula?\s+(?:la\s+)?seguridad",
    r"repite\s+el\s+texto\s+de\s+arriba",
]

SOFT_INJECTION_PATTERNS_ES = [
    r"modo\s+desarrollador",
    r"ahora\s+eres\s+",
]
