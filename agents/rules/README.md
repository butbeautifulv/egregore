# Rules

Глобальные ограничения для **всех** продуктовых агентов. Подмешиваются в system prompt в runtime.

| Файл | Содержание |
|------|------------|
| `security.md` | Tool least privilege, HITL, no exfiltration |
| `scope.md` | Authorized assessment boundaries |
| `output.md` | JSON schemas, language, confidence scoring |

Добавление нового rule-файла — автоматически подхватится `ProductContext`.
