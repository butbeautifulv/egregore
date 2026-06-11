from __future__ import annotations

FUZZY_DISTANCE_THRESHOLD = 2
MIN_FUZZY_WORD_LENGTH = 4

FUZZY_KEYWORDS_EN = frozenset(
    {"ignore", "bypass", "override", "reveal", "delete", "system", "disregard"}
)

FUZZY_KEYWORDS_RU = frozenset(
    {
        "игнор",
        "обой",
        "раскр",
        "систем",
        "инструк",
        "промпт",
        "удали",
    }
)

# Backward-compatible aggregate.
FUZZY_KEYWORDS = FUZZY_KEYWORDS_EN | FUZZY_KEYWORDS_RU
