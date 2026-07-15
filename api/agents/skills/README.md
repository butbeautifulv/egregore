# Product skills

Domain knowledge modules для on-demand загрузки (Skill Gateway).

## Три слоя (см. [AGENTS.md](../../AGENTS.md))

| Слой | Путь | Runtime? |
|------|------|----------|
| **Generic hub** | `shared/skills/agent/*` (cxado meta-repo) | Нет — Cursor via `make skills-install` |
| **Product overlay** | `agents/skills/` (this dir) | **Да** — thin integration on hub |
| **Core rules** | `shared/agent-rules/core/` | Нет — `.agents/rules/core-*.mdc` symlinks |

Security skills (`ai-agent-security`, `prompt-injection-defense`, `rag-security`, `skill-supply-chain`) extend generic hub skills with cys-agi paths.

| Skill | Когда использовать |
|-------|-------------------|
| `ai-agent-security` | Tool abuse, HITL, memory, multi-agent, adversarial testing |
| `prompt-injection-defense` | Direct/indirect injection, jailbreak, guardrails |
| `rag-security` | RAG pipeline: poisoning, ACL, vector store, agent+retrieval |
| `secure-deployment` | Zero trust, mTLS A2A, container hardening, prod config |
| `skill-supply-chain` | External skill/MCP vetting, Cisco AI Defense tooling |
| `ci-cd-threats` | GitHub Actions, supply chain, workflow risks |
| `network-beaconing` | NetFlow, DNS, C2 beaconing patterns |
| `compliance-frameworks` | SOC 2, ISO 27001, NIST CSF mapping |

Coordinator: `skills=["./agents/skills/"]` в runtime.
