# Keycloak role → API surface matrix (as-is)

Documented before OpenFGA object ACL. Roles from `bootstrap/settings.py` defaults.

| Role | Default name | Surfaces |
|------|--------------|----------|
| Ingress | `egregore-ingress` | `POST /events`, work-order create/list, engagement create/list, `/v1/memory`, runs, SSE, promote-plan |
| Reader | `egregore-reader` | `/status`, investigations list/detail/jobs, catalog GET, work-order list/detail, follow-ups GET, tenant memory list |
| Operator | `egregore-operator` | Catalog PUT/DELETE/seed/reload, follow-up POST, HITL resume, pending approvals |
| Gateway | `egregore-gateway` | Tool gateway `POST /invoke` |

## List endpoints

Read/list endpoints now use `egregore-reader`; `egregore-ingress` remains for event/work-order creation and plan promotion.

## After OpenFGA

Object ACL (`can_view` / `can_edit` / `can_operate` / `can_query`) replaces most operator catalog power. Keycloak roles remain for bootstrap (`platform_admin`) and M2M gateway.
