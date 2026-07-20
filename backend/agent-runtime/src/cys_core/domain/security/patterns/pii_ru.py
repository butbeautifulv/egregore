from __future__ import annotations

PII_PATTERNS_RU: list[tuple[str, str]] = [
    (r"\b\d{3}-\d{3}-\d{3}\s+\d{2}\b", "[SNILS_REDACTED]"),
    (r"\b\d{11}\b", "[SNILS_REDACTED]"),
    (r"\b(?:\+7|8|7)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b", "[PHONE_REDACTED]"),
    (r"\b\d{4}\s+\d{6}\b", "[PASSPORT_REDACTED]"),
    (r"\b(?:\d{10}|\d{12})\b", "[INN_REDACTED]"),
]

SENSITIVE_KEY_PATTERNS_RU: list[tuple[str, str]] = [
    (r"парол\w*\s*[:=]\s*\S+", "пароль=[REDACTED]"),
    (r"токен\w*\s*[:=]\s*\S+", "токен=[REDACTED]"),
    (r"секрет\w*\s*[:=]\s*\S+", "секрет=[REDACTED]"),
    (r"ключ\w*\s*[:=]\s*\S+", "ключ=[REDACTED]"),
]

SENSITIVE_KEYS_RU = frozenset({"пароль", "токен", "секрет", "ключ", "учетные_данные"})
