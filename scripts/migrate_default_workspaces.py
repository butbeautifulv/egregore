#!/usr/bin/env python3
"""Create default workspaces for existing organizations/tenants.

Set EGREGORE_DEFAULT_WORKSPACE_ORGS=org1,org2 to drive the migration
explicitly. When Postgres is reachable, distinct tenant_id values from
the engagements table are included as well.
"""

from __future__ import annotations

import os

from bootstrap.container import get_container
from cys_core.application.use_cases.ensure_default_workspace import (
    ensure_default_workspace,
    workspace_authz_tuples,
)


def _env_organizations() -> set[str]:
    raw = os.getenv("EGREGORE_DEFAULT_WORKSPACE_ORGS", "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def _postgres_engagement_tenants() -> set[str]:
    container = get_container()
    if container.settings.use_memory_fallback:
        return set()
    try:
        import psycopg
    except ImportError:
        return set()
    try:
        with psycopg.connect(container.settings.postgres_url) as conn:
            rows = conn.execute("SELECT DISTINCT tenant_id FROM engagements").fetchall()
    except Exception:
        return set()
    return {str(row[0]).strip() for row in rows if str(row[0]).strip()}


def main() -> None:
    container = get_container()
    orgs = _env_organizations() | _postgres_engagement_tenants()
    if not orgs:
        orgs = {"default"}
    store = container.get_workspace_store()
    authz = container.get_authz_service()
    write_tuples = authz.write_tuples if authz.mode != "off" else None
    for org_id in sorted(orgs):
        workspace = ensure_default_workspace(store, org_id)
        if write_tuples is not None:
            write_tuples(workspace_authz_tuples(workspace))
        print(f"{org_id}: {workspace.id}")


if __name__ == "__main__":
    main()
