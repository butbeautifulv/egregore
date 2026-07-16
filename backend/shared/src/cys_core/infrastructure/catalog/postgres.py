from __future__ import annotations

import json
from typing import Any, cast

import psycopg

from cys_core.domain.catalog.models import (
    AgentCatalogEntry,
    CatalogSource,
    CatalogVersion,
    McpServerEntry,
    PlanCatalogEntry,
    ProfilePack,
    SkillCatalogEntry,
)
from cys_core.infrastructure.catalog.catalog_seed_writer import fan_out_secondary_catalogs
from cys_core.infrastructure.catalog.schema import CATALOG_SCHEMA_SQL


class PostgresAgentCatalog:
    def __init__(self, postgres_url: str) -> None:
        self._postgres_url = postgres_url
        with psycopg.connect(self._postgres_url) as conn:
            conn.execute(CATALOG_SCHEMA_SQL)
            conn.commit()

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self._postgres_url)

    def list_agents(self, *, profile_id: str | None = None, enabled_only: bool = True) -> list[AgentCatalogEntry]:
        clauses = ["1=1"]
        params: list[object] = []
        if profile_id:
            clauses.append("profile_id = %s")
            params.append(profile_id)
        if enabled_only:
            clauses.append("enabled = TRUE")
        sql = f"SELECT payload FROM agent_catalog WHERE {' AND '.join(clauses)} ORDER BY name"
        with self._connect() as conn:
            rows = conn.execute(cast(Any, sql), params).fetchall()
        return [AgentCatalogEntry.model_validate(row[0]) for row in rows]

    def get_agent(self, name: str) -> AgentCatalogEntry | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM agent_catalog WHERE name = %s ORDER BY version DESC LIMIT 1",
                (name,),
            ).fetchone()
        if row is None:
            return None
        return AgentCatalogEntry.model_validate(row[0])

    def upsert_agent(self, entry: AgentCatalogEntry) -> AgentCatalogEntry:
        existing = self.get_agent(entry.name)
        if existing is not None:
            entry.version = existing.version + 1
            entry.quality = existing.quality
        entry.source = CatalogSource.API
        payload = entry.model_dump(mode="json")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_catalog (name, profile_id, payload, version, enabled, updated_at)
                VALUES (%s, %s, %s::jsonb, %s, %s, NOW())
                ON CONFLICT (name, profile_id) DO UPDATE SET
                    payload = EXCLUDED.payload,
                    version = EXCLUDED.version,
                    enabled = EXCLUDED.enabled,
                    updated_at = NOW()
                """,
                (entry.name, entry.profile_id, json.dumps(payload), entry.version, entry.enabled),
            )
            conn.commit()
        return entry

    def delete_agent(self, name: str, *, profile_id: str = "cybersec-soc") -> bool:
        entry = self.get_agent(name)
        if entry is None or entry.profile_id != profile_id:
            return False
        entry.enabled = False
        self.upsert_agent(entry)
        return True

    def upsert_profile(self, profile: ProfilePack) -> ProfilePack:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO profile_packs (id, payload, updated_at)
                VALUES (%s, %s::jsonb, NOW())
                ON CONFLICT (id) DO UPDATE SET payload = EXCLUDED.payload, updated_at = NOW()
                """,
                (profile.id, json.dumps(profile.model_dump(mode="json"))),
            )
            conn.commit()
        return profile

    def list_profiles(self) -> list[ProfilePack]:
        with self._connect() as conn:
            rows = conn.execute("SELECT payload FROM profile_packs ORDER BY id").fetchall()
        return [ProfilePack.model_validate(row[0]) for row in rows]

    def get_version(self, profile_id: str) -> CatalogVersion:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(MAX(version), 0), COUNT(*) FILTER (WHERE enabled)
                FROM agent_catalog WHERE profile_id = %s
                """,
                (profile_id,),
            ).fetchone()
        if row is None:
            return CatalogVersion(profile_id=profile_id, version=0, agent_count=0)
        version, agent_count = row
        return CatalogVersion(profile_id=profile_id, version=int(version or 0), agent_count=int(agent_count or 0))

    def seed(
        self,
        entries: list[AgentCatalogEntry],
        profile: ProfilePack,
        *,
        skills: list[SkillCatalogEntry] | None = None,
        plans: list[PlanCatalogEntry] | None = None,
        mcp_servers: list[McpServerEntry] | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO profile_packs (id, payload, updated_at)
                VALUES (%s, %s::jsonb, NOW())
                ON CONFLICT (id) DO UPDATE SET payload = EXCLUDED.payload, updated_at = NOW()
                """,
                (profile.id, json.dumps(profile.model_dump(mode="json"))),
            )
            for entry in entries:
                payload = entry.model_dump(mode="json")
                conn.execute(
                    """
                    INSERT INTO agent_catalog (name, profile_id, payload, version, enabled, updated_at)
                    VALUES (%s, %s, %s::jsonb, %s, %s, NOW())
                    ON CONFLICT (name, profile_id) DO UPDATE SET
                        payload = EXCLUDED.payload,
                        version = EXCLUDED.version,
                        enabled = EXCLUDED.enabled,
                        updated_at = NOW()
                    """,
                    (entry.name, entry.profile_id, json.dumps(payload), entry.version, entry.enabled),
                )
            conn.commit()
        fan_out_secondary_catalogs(skills=skills, plans=plans, mcp_servers=mcp_servers)
