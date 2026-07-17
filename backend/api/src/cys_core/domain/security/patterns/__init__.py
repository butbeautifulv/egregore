from __future__ import annotations

from cys_core.domain.security.patterns.common import (
    BASE64_TOKEN,
    HARD_COMMON_PATTERNS,
    HEX_TOKEN,
    SOFT_COMMON_PATTERNS,
)
from cys_core.domain.security.patterns.corpus_techniques import (
    HARD_CORPUS_TECHNIQUE_PATTERNS,
    SOFT_CORPUS_TECHNIQUE_PATTERNS,
)
from cys_core.domain.security.patterns.fuzzy_keywords import (
    FUZZY_DISTANCE_THRESHOLD,
    FUZZY_KEYWORDS,
    FUZZY_KEYWORDS_EN,
    FUZZY_KEYWORDS_RU,
    MIN_FUZZY_WORD_LENGTH,
)
from cys_core.domain.security.patterns.injection_de import (
    HARD_INJECTION_PATTERNS_DE,
    SOFT_INJECTION_PATTERNS_DE,
)
from cys_core.domain.security.patterns.injection_en import (
    HARD_INJECTION_PATTERNS_EN,
    SOFT_INJECTION_PATTERNS_EN,
)
from cys_core.domain.security.patterns.injection_es import (
    HARD_INJECTION_PATTERNS_ES,
    SOFT_INJECTION_PATTERNS_ES,
)
from cys_core.domain.security.patterns.injection_fr import (
    HARD_INJECTION_PATTERNS_FR,
    SOFT_INJECTION_PATTERNS_FR,
)
from cys_core.domain.security.patterns.injection_ru import (
    HARD_INJECTION_PATTERNS_RU,
    SOFT_INJECTION_PATTERNS_RU,
)
from cys_core.domain.security.patterns.injection_zh import (
    HARD_INJECTION_PATTERNS_ZH,
    SOFT_INJECTION_PATTERNS_ZH,
)
from cys_core.domain.security.patterns.normalization import (
    TOKEN_PATTERN,
    UNICODE_TAG_CHARS,
    UNICODE_TAG_SMUGGLING_THRESHOLD,
    ZERO_WIDTH_CHARS,
    count_unicode_tags,
    fold_confusables,
    is_mixed_script_smuggling,
    latin_skeleton_for_detection,
    mixed_script_category_count,
    normalize_input,
    strip_combining_marks,
)
from cys_core.domain.security.patterns.pii_common import (
    PII_PATTERNS_COMMON,
    SENSITIVE_KEY_PATTERNS_COMMON,
)
from cys_core.domain.security.patterns.pii_en import PII_PATTERNS_EN
from cys_core.domain.security.patterns.pii_es import PII_PATTERNS_ES
from cys_core.domain.security.patterns.pii_ru import (
    PII_PATTERNS_RU,
    SENSITIVE_KEY_PATTERNS_RU,
    SENSITIVE_KEYS_RU,
)
from cys_core.domain.security.patterns.pii_zh import PII_PATTERNS_ZH

HARD_INJECTION_PATTERNS = (
    HARD_COMMON_PATTERNS
    + HARD_CORPUS_TECHNIQUE_PATTERNS
    + HARD_INJECTION_PATTERNS_EN
    + HARD_INJECTION_PATTERNS_RU
    + HARD_INJECTION_PATTERNS_ES
    + HARD_INJECTION_PATTERNS_DE
    + HARD_INJECTION_PATTERNS_FR
    + HARD_INJECTION_PATTERNS_ZH
)

SOFT_INJECTION_PATTERNS = (
    SOFT_COMMON_PATTERNS
    + SOFT_CORPUS_TECHNIQUE_PATTERNS
    + SOFT_INJECTION_PATTERNS_EN
    + SOFT_INJECTION_PATTERNS_RU
    + SOFT_INJECTION_PATTERNS_ES
    + SOFT_INJECTION_PATTERNS_DE
    + SOFT_INJECTION_PATTERNS_FR
    + SOFT_INJECTION_PATTERNS_ZH
)

INJECTION_PATTERNS = HARD_INJECTION_PATTERNS + SOFT_INJECTION_PATTERNS

PII_PATTERNS: list[tuple[str, str]] = (
    PII_PATTERNS_COMMON
    + PII_PATTERNS_EN
    + PII_PATTERNS_RU
    + PII_PATTERNS_ES
    + PII_PATTERNS_ZH
    + SENSITIVE_KEY_PATTERNS_COMMON
    + SENSITIVE_KEY_PATTERNS_RU
)

SENSITIVE_KEYS = frozenset({"password", "api_key", "token", "secret", "credential"} | SENSITIVE_KEYS_RU)

__all__ = [
    "BASE64_TOKEN",
    "FUZZY_DISTANCE_THRESHOLD",
    "FUZZY_KEYWORDS",
    "FUZZY_KEYWORDS_EN",
    "FUZZY_KEYWORDS_RU",
    "HARD_INJECTION_PATTERNS",
    "HEX_TOKEN",
    "INJECTION_PATTERNS",
    "MIN_FUZZY_WORD_LENGTH",
    "PII_PATTERNS",
    "SENSITIVE_KEYS",
    "SOFT_INJECTION_PATTERNS",
    "TOKEN_PATTERN",
    "UNICODE_TAG_CHARS",
    "UNICODE_TAG_SMUGGLING_THRESHOLD",
    "ZERO_WIDTH_CHARS",
    "count_unicode_tags",
    "fold_confusables",
    "is_mixed_script_smuggling",
    "latin_skeleton_for_detection",
    "mixed_script_category_count",
    "normalize_input",
    "strip_combining_marks",
]
