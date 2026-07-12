# OIDC + OpenFGA Local Development

Egregore keeps auth optional for local work:

```bash
AUTH_ENABLED=0
AUTHZ_MODE=off
```

With those defaults, API, worker, gateway, and UI flows behave as before.

## Keycloak OIDC

Set backend JWT verification for FastAPI and the tool gateway:

```bash
AUTH_ENABLED=1
RBAC_ENABLED=1
KEYCLOAK_ISSUER=http://localhost:8081/realms/egregore
KEYCLOAK_CLIENT_ID=egregore-api
```

Set the UI BFF client separately:

```bash
NEXT_PUBLIC_OIDC_ISSUER=http://localhost:8081/realms/egregore
OIDC_CLIENT_ID=egregore-ui
OIDC_CLIENT_SECRET=
OIDC_REDIRECT_URI=http://localhost:3000/api/auth/callback
```

The UI stores the access token in an httpOnly `egregore_session` cookie and proxies API calls through `/api/egregore`.

## OpenFGA

Start local OpenFGA with the compose profile:

```bash
docker compose -f ../../deploy/compose/egregore-infra.yml --profile fga up -d openfga
```

Then create a store/model with the OpenFGA CLI or API and set:

```bash
AUTHZ_MODE=shadow        # use enforce after tuples are seeded
OPENFGA_API_URL=http://localhost:8088
OPENFGA_STORE_ID=<store-id>
OPENFGA_MODEL_ID=<model-id>
OPENFGA_API_TOKEN=
```

`scripts/sync_idp_membership.py` maps Keycloak groups to `organization#member` or `organization#admin` tuples. Users with IdP role `platform_admin` receive `organization:{id}#platform_admin` tuples.

`scripts/seed_datasource_fga.py` seeds `datasource:*` organization links and workspace consumer grants. Run after deploy:

```bash
cd projects/egregore && uv run python scripts/seed_datasource_fga.py
```

Schedule `sync_idp_membership.py` via cron or Helm Job alongside workspace migration.

## Tool gateway M2M (client credentials)

Workers and the API call the tool gateway with a service account JWT when `AUTH_ENABLED=1`:

```bash
KEYCLOAK_ISSUER=http://localhost:8081/realms/egregore
KEYCLOAK_CLIENT_ID=egregore-gateway
```

The gateway expects the `egregore-gateway` Keycloak role on the token (`tests/tool_gateway/test_gateway_auth.py`). Pass `X-Workspace-Id` on `/invoke` so OpenFGA `can_query` checks are workspace-scoped.

## TUI / CLI tokens

The Operator TUI (`projects/egregore/tui`) does not implement the OIDC BFF cookie flow. For authenticated API calls from scripts or TUI, export a bearer token from Keycloak (password grant or device flow in dev) and set `EGREGORE_API_TOKEN` or pass `Authorization: Bearer …` to `egregore` CLI commands. Keep `AUTH_ENABLED=0` for local smoke tests without Keycloak.
