# OWASP Cheat Sheet Series (upstream)

Vendored from [OWASP/CheatSheetSeries](https://github.com/OWASP/CheatSheetSeries) (`cheatsheets/`). CC-BY-SA-4.0.

| File | Product skill |
|------|---------------|
| [LLM_Prompt_Injection_Prevention_Cheat_Sheet.md](LLM_Prompt_Injection_Prevention_Cheat_Sheet.md) | `prompt-injection-defense` |
| [AI_Agent_Security_Cheat_Sheet.md](AI_Agent_Security_Cheat_Sheet.md) | `ai-agent-security` |
| [RAG_Security_Cheat_Sheet.md](RAG_Security_Cheat_Sheet.md) | `rag-security` |
| [Software_Supply_Chain_Security_Cheat_Sheet.md](Software_Supply_Chain_Security_Cheat_Sheet.md) | `skill-supply-chain` (partial; see also CISCO appendix) |
| [Zero_Trust_Architecture_Cheat_Sheet.md](Zero_Trust_Architecture_Cheat_Sheet.md) | `secure-deployment` |

Regenerate skill `reference.md` stubs:

```bash
uv run python scripts/generate_owasp_skills.py
```

Adapted summaries also live in parent [docs/reference/](../) for historical edits.
