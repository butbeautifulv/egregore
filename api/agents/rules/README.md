# Rules

Reference copies of **immutable** global constraints for all product agents.

**Runtime source of truth:** `cys_core/domain/security/immutable_rules.py` (`GLOBAL_RULES_BODY`).
Changes here must be synced to that module (see `tests/domain/security/test_immutable_rules_sync.py`).

| File | Содержание |
|------|------------|
| `security.md` | Tool least privilege, HITL, no exfiltration |
| `scope.md` | Authorized assessment boundaries |
| `output.md` | JSON schemas, language, confidence scoring |

`ProductContext._load_rules()` remains for docs parity checks only; assembly uses `system_prompt_assembler`.
