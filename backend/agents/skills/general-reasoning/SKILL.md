---
name: general-reasoning
description: Domain-agnostic plan discipline, uncertainty reporting, and step-by-step execution
---

# General reasoning discipline

- Read `todo_snapshot` before choosing tools; update statuses every turn.
- Prefer one focused tool call per turn when `strict_plan` is true.
- Report uncertainty explicitly; never fabricate tool outputs.
- Use `load_skill` for domain playbooks instead of guessing procedures.
- Call `reasoning_check` before closing multi-step tasks.
