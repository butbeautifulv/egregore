# ADR-004: Immutable prompt rules (GLOBAL_RULES / SECURITY_RULES)

## Status

Accepted

## Context

Dynamic agent catalog stores full `system_prompt` in Postgres, including `GLOBAL_RULES` and `SECURITY_RULES`. API updates can strip or replace these sections, breaking the security-first contract.

## Decision

1. **Persona-only storage** — catalog persists `persona_prompt` (+ `language` metadata), not baked rule sections.
2. **Backend source of truth** — `GLOBAL_RULES_BODY` and `SECURITY_RULES_BLOCK` live in `cys_core/domain/security/` and are injected at assemble time.
3. **Runtime assembly** — `entry_to_definition()` always calls `assemble_trusted_system_context()`; stored digest is not trusted.
4. **Write gate** — API/catalog writes strip embedded rule markers, persist `persona_prompt` only.
5. **Defense in depth** — `PromptContextMiddleware` refuses LLM calls if system message lacks `GLOBAL_RULES:` / `SECURITY_RULES:` markers.

## Prompt layers

| Layer | Mutable | Source |
|-------|---------|--------|
| `SYSTEM_INSTRUCTIONS` | Yes | `persona_prompt` (AGENT.md, Langfuse, API) |
| `GLOBAL_RULES` | No | `immutable_rules.GLOBAL_RULES_BODY` |
| `SECURITY_RULES` | No | `prompt_context.SECURITY_RULES_BLOCK` |
| `LANGUAGE_SUFFIX` | No | assembler when `language == "ru"` |

## Rollout

1. Deploy assembler + `entry_to_definition` (runtime fix without DB migration).
2. Deploy write gate persona-only persistence.
3. Run `scripts/migrate_catalog_persona_prompts.py --apply`.
4. Middleware marker guard ships with assembler wiring.

## Consequences

- `agents/rules/*.md` remain reference docs; runtime uses Python constants.
- Re-seed or API upsert required to update persona; rules update with backend deploy.
- Digest always computed from assembled prompt via `compute_system_digest()`.
