---
name: skill-supply-chain
description: Vet external agent skills and MCP servers for prompt injection, hidden instructions, and auto-exec risk. Use when onboarding third-party skills, reviewing skill packs, assessing MCP tool security, or applying Cisco AI Defense tooling guidance.
---

# Skill & MCP Supply Chain Security

## When to use

- Onboarding external/community skill packs
- Reviewing MCP server permissions and behavior
- Pre-release skill vetting in CI
- Investigating suspicious skill content or hidden instructions
- Supply chain audit of agent capabilities

## cys-agi skill lifecycle

| Stage | Location | Loaded at runtime? |
|-------|----------|-------------------|
| Builtin (signed) | `agents/skills/` | Yes — via SkillRegistry |
| External staging | `agents/skills/external/staging/` | **No** — never direct load |
| Vetted external | pinned in `agents/manifest.yaml` | Yes — after approval |

### Vetting checklist (required before runtime)

1. SHA-256 hash recorded in registry manifest
2. Prompt injection scan (`source=skill`) on full `SKILL.md` body
3. Cisco Skill Scanner / manual review for `scripts/` auto-exec risk
4. Human L3 approval for `trust_tier: community`
5. Pin `version` + `hash` in `agents/manifest.yaml` — CI blocks drift

### Runtime rules

- Metadata only in agent context; body via `load_skill` → Skill Gateway
- Per-persona allowlist in `agent.yaml` `skills:`
- Audit topic: `audit.skill.loads`

## Threat patterns in skills/MCP

| Risk | Indicator |
|------|-----------|
| Hidden instructions | Base64/Unicode-obfuscated commands in SKILL.md or scripts |
| Prompt injection | "Ignore previous", role hijack, exfiltration via tool params |
| Over-permissioned MCP | Wildcard shell, unrestricted file/network access |
| Auto-exec scripts | `scripts/` that run shell/code without explicit user trigger |
| Dependency drift | Unpinned versions, `@main` actions, floating tags |
| Data exfiltration | Skill instructs agent to send context to external URL |

## MCP tool hardening

**Bad:** unrestricted shell — `allowed_commands: "*"`.

**Good:** scoped access — path allowlists, read-only ops, blocked patterns (`*.env`, `*.key`, `*secret*`).

Apply same least-privilege as native tools; separate tool sets by trust level.

## Cisco AI Defense tooling (reference)

| Tool | Purpose |
|------|---------|
| [Skill Scanner](https://github.com/cisco-ai-defense/skill-scanner) | Malicious behaviors, hidden instructions in agent skills |
| [MCP Scanner](https://github.com/cisco-ai-defense/mcp-scanner) | MCP server behavioral threat analysis |
| [A2A Scanner](https://github.com/cisco-ai-defense/a2a-scanner) | Agent-to-agent communication threats |
| [DefenseClaw](https://github.com/cisco-ai-defense/defenseclaw) | Governance — scan/enforce/audit skills, MCP, plugins |
| [AI BOM](https://github.com/cisco-ai-defense/aibom) | AI Bill of Materials via dependency scan |

Framework: [Integrated AI Security and Safety Framework](https://arxiv.org/abs/2512.12921)

## Review workflow

1. Stage pack in `external/staging/` — do not add to manifest yet
2. Hash SKILL.md + all bundled files; record in manifest draft
3. Run injection scan on full body (not metadata alone)
4. Review `scripts/` for auto-exec, network calls, credential access
5. Compare requested tools vs persona allowlist — reject scope creep
6. L3 sign-off for community tier; pin version+hash; enable in persona `skills:`

## Output guidance

- Report: hash, trust tier, injection scan result, script risk, approval status.
- Block runtime load until all checklist items pass.
- Never promote staging content directly to `agents/skills/` without vetting.
- For MCP: document allowed operations, blocked paths, and HITL requirements.

## Deep reference

- [reference.md](reference.md) — OWASP supply chain + agent skill vetting
- [docs/reference/owasp/Software_Supply_Chain_Security_Cheat_Sheet.md](../../../docs/reference/owasp/Software_Supply_Chain_Security_Cheat_Sheet.md)
- `docs/SKILLS_VETTING.md`
- [docs/reference/CISCO_AI_DEFENCE.md](../../../docs/reference/CISCO_AI_DEFENCE.md)
