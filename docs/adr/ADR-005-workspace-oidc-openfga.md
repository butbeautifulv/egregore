# ADR-005: Workspace, OIDC AuthN, OpenFGA ReBAC

## Status

Accepted

## Context

Egregore today has optional Keycloak JWT validation and coarse global RBAC (`egregore-reader|operator|ingress|gateway`). Catalog mutations and data access are not object-scoped. `tenant_id` is caller-supplied and not bound to JWT. `profile_id` selects a product pack (e.g. `cybersec-soc`), not a user workspace.

Operators need personal/team **workspaces** with custom worker personas while keeping control agents (`planner`, `critic`, `coordinator`) view-only and datasources (SIEM/Veil) explicitly granted.

## Decision

### Separation of concerns

| Layer | Responsibility |
|-------|----------------|
| Keycloak (OIDC) | AuthN: identity, MFA, JWT (`sub`, email, org/groups) |
| OpenFGA | AuthZ: ReBAC `Check(user, relation, object)` |
| Domain | Workspace, catalog, engagements, datasource grants |
| ADR-004 | Immutable `GLOBAL_RULES` / `SECURITY_RULES` — never workspace-editable |

### Identity vs configuration

| Concept | Meaning |
|---------|---------|
| `organization_id` | Auth boundary (maps from JWT; wire alias `tenant_id` during migration) |
| `workspace_id` | User/team context for custom worker prompts and engagements |
| `profile_id` | Product pack / policy profile — **not** a workspace |

### Control vs workers

- Platform control agents: **view-only** (code deny + no FGA `can_edit`).
- Workers: fork into `workspace_agent` then edit under `can_edit`.
- Datasources: explicit FGA `can_query` grants; never auto-granted on workspace create.

### Feature flags

- `AUTH_ENABLED` — JWT verification
- `AUTHZ_MODE=off|shadow|enforce` — OpenFGA; fail-closed when `enforce` and FGA unavailable

## Consequences

- New domain `Workspace`, stores, APIs, UI picker.
- Catalog write path must deny control mutate and route worker edits through workspace agents.
- Tool gateway checks FGA datasource grants AND profile/persona allowlists.
- IdP sync writes membership tuples only (never tool permissions from LDAP).

## Threat model (summary)

See appendix below and `docs/auth/role-matrix-as-is.md`.

### Cross-tenant access

Mitigation: bind `tenant_id` / `organization_id` to JWT claims; reject mismatch (Phase 1).

### Datasource overgrant

Mitigation: no automatic SIEM grant on workspace create; org admin grants only.

### Control-agent edit

Mitigation: hard deny list + FGA model without `can_edit` on platform control agents.

### Workspace prompt injection

Mitigation: ADR-004 assembler; `CatalogWriteGate` strips embedded rule sections; persona-only storage.

### IdP → permissions confusion

Mitigation: sync membership only; never sync `can_query` from LDAP groups.

## IdP sync contract

Keycloak groups/orgs → `organization#member` / `admin` tuples only. Platform admin role → FGA `platform_admin` mapping. Never sync tool or datasource execute permissions from LDAP.
