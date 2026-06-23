---
name: ai-agent-security
description: Secure AI agent architectures — tool least privilege, HITL, memory isolation, output guardrails, multi-agent trust, monitoring, and adversarial testing. Use when designing, reviewing, or hardening agent systems; assessing tool abuse, goal hijacking, memory poisoning, cascading failures, or excessive autonomy.
---

# AI Agent Security

## When to use

- Agent architecture review or threat modeling
- Tool/MCP permission scoping and HITL design
- Memory, context, and multi-agent bus security
- Pre-production adversarial validation planning
- Incident triage for agent misbehavior or privilege escalation

## Key risks

| Risk | Signal |
|------|--------|
| Prompt injection (direct/indirect) | Instructions in user input, telemetry, or retrieved docs override system prompt |
| Tool abuse / privilege escalation | Agent calls tools outside scope or with attacker-controlled params |
| Data exfiltration | Sensitive data in tool calls, URLs, logs, or outputs |
| Memory poisoning | Malicious content persisted and affects future sessions |
| Goal hijacking | Agent objectives silently redirected while appearing legitimate |
| Excessive autonomy | High-impact actions without human oversight |
| Cascading failures | Compromised agent propagates attack via multi-agent chains |
| Denial of Wallet | Unbounded loops, retries, or token burn |

## Controls (priority order)

### 1. Tool least privilege

- Minimum tools per persona; separate tool sets by trust level.
- Per-tool scoping: read-only vs write, path allowlists, blocked patterns (`*.env`, `*secret*`).
- Never grant wildcard shell/code execution.
- **cys-agi:** tool allowlist in `agent.yaml`; dangerous tools in `hitl_tools`; sandbox-scoped MCP in `mcp_tools.py`.

### 2. Input validation

- Treat all external data as untrusted: user messages, SIEM alerts, documents, API responses, emails.
- Sanitize before LLM context; use delimiters separating instructions from data.
- **cys-agi:** ingress sanitization + `cys_core/domain/security/patterns/` (injection, PII, normalization).

### 3. Memory & context

- Validate before persistence; isolate per user/session; TTL and size limits.
- Scan for injection patterns and sensitive data before store.
- Integrity checksums for long-term memory entries.

### 4. Human-in-the-loop (HITL)

Classify actions by risk:

| Level | Examples | Control |
|-------|----------|---------|
| LOW | read, search | Auto-approve |
| MEDIUM | write, API call | Log + optional approval |
| HIGH | email, execute, external comms | Require approval |
| CRITICAL | delete, funds, privilege change | Step-up auth + bound approval |

- Bind approval to exact action (actor, tool, target, params, timestamp, expiry).
- Separate decision from execution; fail closed on policy/audit failure.
- **cys-agi:** `run_active_scan`, `write_file` require HITL when configured.

### 5. Output validation

- Schema-validate structured outputs (Pydantic/JSON Schema).
- Filter PII/secrets from responses and logs.
- Rate-limit tool calls; detect exfiltration patterns (base64 in URLs, oversized webhook payloads).
- Never use model output alone for authorization.

### 6. Multi-agent security

- Trust boundaries between agents; sign and verify inter-agent messages.
- Replay protection (timestamp window), recipient validation, payload sanitization by trust level.
- Circuit breakers to stop cascading failures.
- **cys-agi:** `SecureAgentBus` — A2A envelopes, HMAC signing, trust levels, mTLS identities.

### 7. Monitoring

Log: decisions, tool calls, risk classification, approval outcome, policy version.
Alert on: injection attempts, approval bypass, privilege escalation, anomalous tool frequency, cost spikes.

### 8. Adversarial testing (pre-prod gate)

| Abuse case | Validate |
|------------|----------|
| Prompt override | System instructions not replaced by user/retrieved content |
| Tool misuse | Unauthorized tools denied despite confident model request |
| Privilege escalation | Low-trust session cannot reach privileged tools |
| Memory poisoning | Malicious content sanitized/rejected before persistence |
| Data exfiltration | No leak via tool calls, citations, logs, output |
| Recursive tool abuse | Chain depth, retry, token, cost limits enforced |
| Approval bypass | High-impact actions blocked without valid approval |
| Multi-agent chaining | Compromised agent cannot exceed peer trust boundary |

Run in CI/CD after prompt, tool, memory, retrieval, or provider changes.

## Output guidance

- Map findings to specific control gaps (tool scope, HITL, memory, bus, monitoring).
- Distinguish theoretical risk from exploitable path with preconditions.
- Recommend compensating controls when full mitigation is impractical.
- Reference `agents/rules/security.md` for platform baseline constraints.

## Deep reference

- [reference.md](reference.md) — OWASP upstream pointer
- [docs/reference/owasp/AI_Agent_Security_Cheat_Sheet.md](../../../docs/reference/owasp/AI_Agent_Security_Cheat_Sheet.md)
- Adapted summary: [docs/reference/AI_Agent_Security_Cheat_Sheet.md](../../../docs/reference/AI_Agent_Security_Cheat_Sheet.md)
