# Injection corpus (threat intel, read-only)

Локальный корпус известных jailbreak/injection-примеров для **offline triage** при расширении фильтров.

## Расположение

Корпус хранится локально в [`docs/injections/`](../../injections/) (в `.gitignore`, не коммитится).

## Правила безопасности

1. **Не runtime-конфиг** — код приложения не импортирует и не читает эти файлы.
2. **Не копировать payloads** в Python, тесты, коммиты, логи или PR.
3. **Triage = категории**, не дословные строки: `instruction_override`, `role_hijack`, `prompt_extraction`, `encoding_obfuscation`, `special_token`, и т.д.
4. **AI-ассистентам** — не открывать файлы корпуса без явного запроса; многие содержат adversarial unicode и social engineering.
5. **Тесты** — только синтетические минимальные строки по семантике категории.

## Offline triage

```bash
uv run python scripts/triage_injection_corpus.py
```

Скрипт выводит только метаданные (количество файлов, скрипты, флаги obfuscation) — **без содержимого**.

## Связь с кодом

Паттерны фильтрации: `cys_core/domain/security/patterns/` (injection_*, pii_*, normalization).
