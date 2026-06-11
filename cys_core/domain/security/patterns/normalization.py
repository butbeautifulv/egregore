from __future__ import annotations

import re
import unicodedata

# Zero-width, bidi overrides, variation selectors.
ZERO_WIDTH_CHARS = re.compile(
    "["
    "\u200b-\u200f"
    "\u202a-\u202e"
    "\u2060-\u2064"
    "\ufeff"
    "\u2066-\u2069"
    "\ufe00-\ufe0f"
    "]"
)

# Cyrillic letters that look like Latin (fold to Latin for cross-script matching).
_CYRILLIC_TO_LATIN = str.maketrans(
    {
        "\u0430": "a",
        "\u0435": "e",
        "\u043e": "o",
        "\u0440": "p",
        "\u0441": "c",
        "\u0443": "y",
        "\u0445": "x",
        "\u0410": "a",
        "\u0415": "e",
        "\u041e": "o",
        "\u0420": "p",
        "\u0421": "c",
        "\u0423": "y",
        "\u0425": "x",
    }
)

TOKEN_PATTERN = re.compile(r"[\w\u0400-\u04FF]+", re.UNICODE)


def fold_confusables(text: str) -> str:
    """Map Cyrillic homoglyphs to Latin only in mixed-script tokens (e.g. ignоre)."""
    tokens = TOKEN_PATTERN.findall(text)
    if not tokens:
        return text
    result = text
    for token in tokens:
        has_ascii = any("A" <= ch <= "Z" or "a" <= ch <= "z" for ch in token)
        has_cyrillic = any("\u0400" <= ch <= "\u04FF" for ch in token)
        if has_ascii and has_cyrillic:
            folded = token.translate(_CYRILLIC_TO_LATIN)
            if folded != token:
                result = result.replace(token, folded, 1)
    return result


def normalize_input(content: str) -> str:
    """Full normalization pipeline for injection detection."""
    content = unicodedata.normalize("NFKC", content)
    content = ZERO_WIDTH_CHARS.sub(" ", content)
    content = fold_confusables(content)
    content = re.sub(r"\s+", " ", content)
    content = re.sub(r"(.)\1{3,}", r"\1", content)
    return content.strip()
