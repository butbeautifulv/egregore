# Secure deployment model

## Security goals

cys-agi deployment follows zero-trust, MILS, and least-privilege principles:

- distrust every input, peer, network, and storage backend by default;
- isolate product agents from infrastructure connectors;
- keep domain/application code independent from storage and model vendors;
- require A2A envelopes and mTLS identities for inter-agent traffic;
- run containers as non-root with minimal Linux capabilities;
- keep the async runtime suitable for FastAPI/ASGI behind a hardened reverse proxy.

## MILS partitions

| Partition | Code / asset | Trust boundary |
|-----------|--------------|----------------|
| Domain | `cys_core/domain/` | Pure business/security policy, no I/O |
| Application ports | `cys_core/application/ports.py` | Dependency inversion boundary |
| Infrastructure connectors | `cys_core/persistence.py`, `cys_core/llm/` | Swappable storage/model backends |
| Interface adapters | `graph/`, `coordinator/`, `main.py` | CLI/graph/coordinator composition |
| Product content | `agents/` | Personas/rules/plans/skills loaded as data |
| Deployment shell | `Dockerfile`, `docker-compose.secure.yml`, `deploy/` | Container and network isolation |

## Connectors

Runtime code depends on ports, not concrete backends:

- `PersistenceConnector`: `auto`, `memory`, `postgres`
- `ModelConnector`: current `litellm`, swappable by registering another connector
- `AgentTransportConnector`: A2A transport contract with mandatory mTLS flag

Configure persistence with:

```bash
PERSISTENCE_CONNECTOR=auto|memory|postgres
```

## A2A + mTLS

`SecureAgentBus` emits A2A envelopes:

- `protocol`: `a2a/1.0`
- signed sender/recipient/type/payload/timestamp
- `mtls.required=true`
- SPIFFE-style default identities: `spiffe://cys-agi/agent/<agent_id>`

Receivers validate:

1. A2A protocol version
2. HMAC signature
3. replay window
4. intended recipient
5. expected recipient mTLS subject

Networked deployments should terminate or pass through mTLS at the agent transport layer and forward verified peer identity into the A2A transport connector.

## Container hardening

`Dockerfile` uses:

- multi-stage build;
- dependency install in builder stage;
- `compileall` for Python modules;
- minimal runtime stage;
- non-root UID/GID `10001`;
- no shell entrypoint.

`docker-compose.secure.yml` adds:

- `read_only: true`;
- `cap_drop: [ALL]`;
- `no-new-privileges`;
- seccomp profile;
- tmpfs for writable runtime paths;
- internal-only network for agent/storage traffic;
- reverse proxy on an edge network.

## Reverse proxy

`deploy/nginx/cys-agi.conf` is prepared for a future FastAPI/ASGI API:

- TLS 1.3 only;
- client certificate verification;
- HSTS and defensive headers;
- small request body limits;
- forwarded mTLS identity headers.

## Deep Agents sandbox

Deep Agents runs only with configured tools and product skills:

- tool allowlist is loaded from `agents/personas/*/agent.yaml`;
- dangerous tools require HITL (`run_active_scan`, `write_file`);
- async middleware enforces scope, rate limits, and risk gates;
- product content remains data under `agents/`, not Python modules.

For stronger runtime sandboxing, run the container with the secure compose profile and keep all mutable data behind connectors.

## FastAPI-ready async entrypoints

Use async entrypoints from a future FastAPI app:

```python
await run_assessment_async(...)
await run_session_async(...)
await AgentRuntime().arun(...)
```

Do not call sync compatibility wrappers from ASGI request handlers.
