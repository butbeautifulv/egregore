# egregore-tool-gateway

The MCP Tool Gateway — the policy-enforcement point (PEP) for sandboxed
agent tool calls (SIEM/RAG/web/files/sandbox/veil/nessus). Serves
`GET /health`, `GET /metrics`, `POST /invoke` over a small stdlib
`asyncio.start_server`-based HTTP layer — no FastAPI/Starlette/aiohttp.

No agent-execution frameworks (langchain/langchain-core/langgraph/
deepagents/litellm) — every tool it can invoke is a plain-function adapter
in `cys_core/infrastructure/tools/adapters/`, extracted from worker's
LangChain-typed tool registry with zero duplication (the registry's own
`@tool` wrappers delegate to the same functions). See
`docs/MSP_BACKLOG.md` §21 for the full history: §21.1–§21.2
(langchain-core removed from `api`, FastAPI replaced in worker's original
in-package gateway), §21.5 (registry decoupled from the gateway's execution
path), §21.6 (this package extracted, physical-copy pattern matching
`api`/`worker`, trimmed to only what `interfaces/gateways/tool/` reaches).

Fully self-contained — its own physical copy of domain models, port
interfaces, and generic infra clients (no shared package with
`egregore-api`/`egregore-worker`). Run: `egregore tool-gateway [--host]
[--port]`, or `make dev-tool-gateway` from the repo root.
