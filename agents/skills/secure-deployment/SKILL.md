---
name: secure-deployment
description: Zero-trust deployment for cys-agi — MILS partitions, mTLS A2A bus, container hardening, connector isolation, and production config. Use when deploying to production, reviewing infrastructure security, or hardening agent platform boundaries.
---

# Secure Deployment (cys-agi)

## When to use

- Production deployment planning or review
- Zero-trust / least-privilege architecture decisions
- A2A bus, mTLS, or inter-agent transport hardening
- Container and reverse-proxy configuration
- Connector and persistence backend selection

## Security goals

- Distrust every input, peer, network, and storage backend by default
- Isolate product agents from infrastructure connectors
- Domain code independent of storage/model vendors
- A2A envelopes + mTLS for inter-agent traffic
- Non-root containers, minimal Linux capabilities
- Fail-closed when Postgres or signing keys unavailable in prod

## MILS partitions

| Partition | Path | Trust boundary |
|-----------|------|----------------|
| Domain | `cys_core/domain/` | Pure policy, no I/O |
| Application ports | `cys_core/application/ports.py` | Dependency inversion |
| Infrastructure | `cys_core/persistence.py`, `cys_core/llm/` | Swappable backends |
| Interfaces | `interfaces/` | API, ingress, workers, gateways, CLI |
| Product content | `agents/` | Personas/rules/plans/skills as data |
| Deployment shell | `Dockerfile`, `docker-compose.secure.yml`, `deploy/` | Container/network isolation |

## Zero Trust principles (apply to agent platform)

1. All resources need protection — no implicit internal trust
2. Encrypt and authenticate all communication (TLS 1.3+)
3. Per-session access — short-lived, re-evaluated
4. Dynamic policy — identity, device, location, behavior, time
5. Continuous monitoring — posture drift revokes access
6. Strict real-time authZ — no permanent admin rights
7. Collect telemetry for detection and policy improvement

## Production configuration

```bash
PERSISTENCE_CONNECTOR=postgres
JOB_STORE_CONNECTOR=postgres
BUS_SIGNING_KEY=<secret>          # required in prod
USE_MEMORY_FALLBACK=false           # fail-closed if Postgres down
```

Run migrations before first prod start: `cys-agi migrate`

## A2A + mTLS (`SecureAgentBus`)

Envelope fields: `protocol=a2a/1.0`, signed sender/recipient/type/payload/timestamp, `mtls.required=true`.

Default identities: `spiffe://cys-agi/agent/<agent_id>`

Receiver validates:
1. A2A protocol version
2. HMAC signature
3. Replay window
4. Intended recipient
5. Expected mTLS subject

## Container hardening

**Dockerfile:** multi-stage build, `compileall`, non-root UID 10001, minimal runtime.

**docker-compose.secure.yml:**
- `read_only: true`, `cap_drop: [ALL]`, `no-new-privileges`
- seccomp profile, tmpfs for writable paths
- internal network for agent/storage; edge network for reverse proxy

**Reverse proxy** (`deploy/nginx/cys-agi.conf`): TLS 1.3, client cert verification, HSTS, body limits, mTLS identity headers.

## Runtime agent sandbox

- Tool allowlist from `agents/personas/*/agent.yaml`
- HITL on dangerous tools (`run_active_scan`, `write_file`)
- Middleware: scope, rate limits, risk gates
- Product content is data under `agents/`, not Python modules

## Connectors (ports, not concrete backends)

| Connector | Options |
|-----------|---------|
| PersistenceConnector | auto, memory, postgres |
| ModelConnector | litellm (swappable) |
| AgentTransportConnector | A2A with mandatory mTLS |

## Output guidance

- Map deployment gaps to partition boundary violations or missing controls.
- Flag dev defaults (`USE_MEMORY_FALLBACK=true`, missing `BUS_SIGNING_KEY`) as prod blockers.
- Recommend specific hardening: mTLS termination, seccomp, connector fail-closed, HITL enablement.

## Deep reference

- [reference.md](reference.md) — OWASP upstream pointer
- [docs/reference/owasp/Zero_Trust_Architecture_Cheat_Sheet.md](../../../docs/reference/owasp/Zero_Trust_Architecture_Cheat_Sheet.md)
- `docs/SECURE_DEPLOYMENT.md`
- Adapted summary: [docs/reference/Zero_Trust_Architecture_Cheat_Sheet.md](../../../docs/reference/Zero_Trust_Architecture_Cheat_Sheet.md)
