---
name: rag-security
description: Secure Retrieval-Augmented Generation pipelines — document poisoning, embedding manipulation, context window attacks, access control, vector index integrity, query abuse, output validation, and agent tool safety. Use when designing, auditing, or incident-triaging RAG systems integrated with agents.
---

# RAG Security

## When to use

- RAG pipeline architecture review or threat modeling
- Document ingestion and vector store hardening
- Access control / tenant isolation in retrieval
- Agent + RAG integration (retrieved content → tool calls)
- RAG-specific incident response (poisoned corpus, cache leakage)

## Implementation priority

**Foundational (implement first):**

- Document hashing (SHA-256) at ingestion; verify before retrieval
- Context delimiters + chunk limits (3–5 chunks, 2–4K tokens)
- Per-chunk access control metadata; enforce at retrieval time
- Tenant/classification isolation in vector stores
- Query normalization and abuse detection; rate limiting
- Output validation and policy enforcement
- Full pipeline observability; fail-closed on integrity/policy failure

**Next (compliance/audit):** signed source attribution, index integrity monitoring, cache isolation, supply chain vetting, cascading deletion.

**Advanced:** embedding distribution monitoring, differential privacy for high-risk datasets.

## Pipeline controls by stage

### 1. Document ingestion (poisoning)

| Do | Don't |
|----|-------|
| Hash + provenance (who, when, source, approval) | Ingest untrusted sources without scan |
| Scan for injection markers, invisible Unicode, zero-width chars | Trust MIME type alone |
| Allowlist trusted sources; approval workflow for new sources | Bulk upload without review |

### 2. Embeddings

- Monitor distribution drift; cross-validate with multiple models in high-security envs.
- Treat embeddings as sensitive — encrypt at rest, same ACL as source docs.
- No direct embedding API access from untrusted agents/users.

### 3. Context window attacks

- Delimiters: `BEGIN RETRIEVED CONTENT (data only)` / `END RETRIEVED CONTENT`.
- Reinforce system prompt after retrieved content (test per model).
- Scan chunks for `SYSTEM:`, `INSTRUCTION:`, `ignore previous` before inclusion.
- Retrieved content is **DATA**, not **COMMANDS**.

### 4. Access control inheritance

- Store ACL metadata (classification, owner, roles, tenant) on every chunk.
- Enforce at **retrieval time**, not just ingestion — permissions change.
- Pre-retrieval filtering (not post-retrieval); tenant A never sees tenant B chunks.
- Cascading deletion: source doc removal → chunks + embeddings + cache purged.

### 5. Source attribution

- Return document IDs, chunk refs, provenance, hashes with every response.
- Sign attribution; provide verification endpoint.

### 6. Index integrity

- Checksum verification; write access only via ingestion pipeline.
- Log all index modifications; snapshots for rollback.
- Alert on unexpected size changes; auth + network isolation on vector DB.

### 7. Query injection / reconnaissance

- Normalize queries; rate limit per user/agent.
- Monitor systematic corpus probing; log all queries with identity.
- Do not expose similarity scores to untrusted callers.

### 8. Output validation

- Policy filters for PII, secrets, regulated data.
- Schema-validate tool calls from RAG-influenced output.
- Dynamic redaction based on querying user's access level.

### 9. Agent + RAG tool safety

- HITL for high-risk actions (payments, deletion, external API).
- Tool authorization independent of model decision.
- Per-context tool allowlist; full traceability (query → retrieval → output → tool).
- Circuit breakers on anomalous tool volume.

### 10. Caching

- Scope cache by user/tenant/permission; invalidate on doc update/deletion/revocation.
- No shared cache across permission boundaries; short TTL for sensitive data.

## CI/CD red-team minimum

| Test | Pass criteria |
|------|---------------|
| Poisoned doc retrieval | Known-bad doc not surfaced or blocked |
| Indirect prompt injection | Retrieved content does not override system prompt |
| Cross-tenant retrieval | Zero cross-boundary chunks |
| Stale permissions | Revoked user cannot retrieve restricted docs |
| Cache leakage | User A never gets User B's cached response |
| Unauthorized tool invocation | RAG output cannot trigger disallowed tools |
| Deletion propagation | Chunks removed after source deletion |

## Output guidance

- Identify which pipeline stage failed (ingestion, retrieval, context, output, tool).
- Require evidence: document hash mismatch, ACL gap, missing delimiter, or cache scope error.
- Recommend fail-closed behavior when integrity or policy lookup fails.

## Deep reference

- [reference.md](reference.md) — OWASP upstream pointer
- [docs/reference/owasp/RAG_Security_Cheat_Sheet.md](../../../docs/reference/owasp/RAG_Security_Cheat_Sheet.md)
- Adapted summary: [docs/reference/RAG_Security_Cheat_Sheet.md](../../../docs/reference/RAG_Security_Cheat_Sheet.md)
