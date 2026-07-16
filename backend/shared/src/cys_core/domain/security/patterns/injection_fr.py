from __future__ import annotations

HARD_INJECTION_PATTERNS_FR = [
    r"ignor\w*\s+(?:toutes?\s+)?(?:les\s+)?instructions?\s+(?:précédentes?|antérieures?)",
    r"révèle?\s+(?:ton\s+)?(?:prompt|instructions?)\s+(?:du\s+)?système",
    r"tu\s+es\s+maintenant\s+en\s+mode\s+développeur",
    r"contourn\w*\s+(?:la\s+)?sécurité",
    r"répète\s+le\s+texte\s+ci-dessus",
]

SOFT_INJECTION_PATTERNS_FR = [
    r"mode\s+développeur",
    r"tu\s+es\s+maintenant\s+",
]
