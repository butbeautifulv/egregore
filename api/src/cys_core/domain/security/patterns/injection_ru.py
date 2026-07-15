from __future__ import annotations

HARD_INJECTION_PATTERNS_RU = [
    # Instruction override
    r"(?:игнорир\w*|забуд\w*|отмен\w*)\s+(?:все\s+)?(?:предыдущ\w*|ранн\w*|выше\w*)?\s*(?:инструкци\w*|указани\w*|правил\w*)",
    r"не\s+следуй\s+(?:предыдущ\w*|системн\w*)\s*(?:инструкци\w*|правил\w*)",
    # Role hijack
    r"ты\s+теперь\s+(?:в\s+)?(?:режим\w*|рол\w*|администратор\w*|админ\w*|разработчик\w*)",
    r"вы\s+теперь\s+(?:в\s+)?(?:режим\w*|рол\w*)",
    # Prompt extraction
    r"(?:раскрой|выведи|покажи|повтори)\s+(?:свой\s+)?(?:системн\w*\s+)?(?:промпт|инструкци\w*)",
    r"какие\s+(?:были\s+)?(?:твои\s+)?(?:точн\w*\s+)?инструкци\w*",
    r"повтори\s+текст\s+выше",
    # Safety bypass
    r"(?:обойди|отключи|сними)\s+(?:все\s+)?(?:защит\w*|фильтр\w*|ограничени\w*|безопасност\w*)",
    r"новый\s+системн\w*\s+промпт",
    # Transliterated RU (Latin script bypass)
    r"ignorir\w*\s+(?:vse\s+)?(?:predydush\w*|preдыдущ\w*)\s+instrukc\w*",
    r"raskroi\s+(?:svoi\s+)?(?:sistemny\w*\s+)?prompt",
    r"obyid\w*\s+(?:vse\s+)?(?:zashit\w*|ogranichen\w*)",
]

SOFT_INJECTION_PATTERNS_RU = [
    r"ты\s+теперь\s+",
    r"режим\s+разработчик\w*",
    r"режим\s+разработки",
    r"dan\s+mode",
    r"developer\s+mode",
]
