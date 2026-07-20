from __future__ import annotations

from cys_core.domain.catalog.models import (
    McpServerEntry,
    PlanCatalogEntry,
    SkillCatalogEntry,
    ToolCatalogEntry,
)
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.infrastructure.catalog.postgres_json_catalog import PostgresJsonCatalog


def _merge_skill_version(new: SkillCatalogEntry, existing: SkillCatalogEntry) -> None:
    new.version = existing.version + 1
    new.quality = existing.quality


def _merge_plan_version(new: PlanCatalogEntry, existing: PlanCatalogEntry) -> None:
    new.version = existing.version + 1
    new.quality = existing.quality


class PostgresSkillCatalog(PostgresJsonCatalog[SkillCatalogEntry]):
    def __init__(self, postgres_url: str) -> None:
        super().__init__(postgres_url, table="skill_catalog", model_class=SkillCatalogEntry)

    def list_skills(
        self, *, profile_id: str | None = None, enabled_only: bool = True
    ) -> list[SkillCatalogEntry]:
        return self.list_items(profile_id=profile_id, enabled_only=enabled_only)

    def get_skill(self, skill_id: str, *, profile_id: str = DEFAULT_PROFILE_ID) -> SkillCatalogEntry | None:
        return self.get_item(skill_id, profile_id=profile_id)

    def upsert_skill(self, entry: SkillCatalogEntry) -> SkillCatalogEntry:
        return self.upsert_item(entry, merge=_merge_skill_version, versioned=True)

    def delete_skill(self, skill_id: str, *, profile_id: str = DEFAULT_PROFILE_ID) -> bool:
        entry = self.get_skill(skill_id, profile_id=profile_id)
        if entry is None:
            return False
        entry.enabled = False
        self.upsert_skill(entry)
        return True

    def increment_usage(self, skill_id: str, *, profile_id: str = DEFAULT_PROFILE_ID, error: bool = False) -> None:
        entry = self.get_skill(skill_id, profile_id=profile_id)
        if entry is None:
            return
        if error:
            entry.quality.load_errors += 1
        else:
            entry.quality.usage_count += 1
        self.upsert_skill(entry)


class PostgresPlanCatalog(PostgresJsonCatalog[PlanCatalogEntry]):
    def __init__(self, postgres_url: str) -> None:
        super().__init__(postgres_url, table="plan_catalog", model_class=PlanCatalogEntry)

    def list_plans(
        self, *, profile_id: str | None = None, enabled_only: bool = True
    ) -> list[PlanCatalogEntry]:
        return self.list_items(profile_id=profile_id, enabled_only=enabled_only)

    def get_plan(self, plan_id: str, *, profile_id: str = DEFAULT_PROFILE_ID) -> PlanCatalogEntry | None:
        return self.get_item(plan_id, profile_id=profile_id)

    def load_active(self, profile_id: str = DEFAULT_PROFILE_ID) -> list[PlanCatalogEntry]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload FROM plan_catalog
                WHERE profile_id = %s AND enabled = TRUE AND active = TRUE
                ORDER BY id
                """,
                (profile_id,),
            ).fetchall()
        if rows:
            return [PlanCatalogEntry.model_validate(row[0]) for row in rows]
        return self.list_plans(profile_id=profile_id, enabled_only=True)

    def upsert_plan(self, entry: PlanCatalogEntry) -> PlanCatalogEntry:
        return self.upsert_item(
            entry,
            merge=_merge_plan_version,
            versioned=True,
            extra_columns=("active",),
        )

    def activate_plan(self, plan_id: str, *, profile_id: str = DEFAULT_PROFILE_ID) -> PlanCatalogEntry | None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE plan_catalog SET active = FALSE WHERE profile_id = %s",
                (profile_id,),
            )
            conn.execute(
                "UPDATE plan_catalog SET active = TRUE WHERE id = %s AND profile_id = %s",
                (plan_id, profile_id),
            )
            conn.commit()
        return self.get_plan(plan_id, profile_id=profile_id)


class PostgresMcpServerCatalog(PostgresJsonCatalog[McpServerEntry]):
    def __init__(self, postgres_url: str) -> None:
        super().__init__(postgres_url, table="mcp_server_catalog", model_class=McpServerEntry)

    def list_servers(
        self, *, profile_id: str | None = None, enabled_only: bool = True
    ) -> list[McpServerEntry]:
        return self.list_items(profile_id=profile_id, enabled_only=enabled_only)

    def get_server(self, server_id: str, *, profile_id: str = DEFAULT_PROFILE_ID) -> McpServerEntry | None:
        return self.get_item(server_id, profile_id=profile_id)

    def upsert_server(self, entry: McpServerEntry) -> McpServerEntry:
        return self.upsert_item(entry)


class PostgresToolCatalog(PostgresJsonCatalog[ToolCatalogEntry]):
    def __init__(self, postgres_url: str) -> None:
        super().__init__(postgres_url, table="tool_catalog", model_class=ToolCatalogEntry)

    def list_tools(
        self, *, profile_id: str | None = None, enabled_only: bool = True
    ) -> list[ToolCatalogEntry]:
        return self.list_items(profile_id=profile_id, enabled_only=enabled_only)

    def get_tool(self, tool_id: str, *, profile_id: str = DEFAULT_PROFILE_ID) -> ToolCatalogEntry | None:
        return self.get_item(tool_id, profile_id=profile_id)

    def upsert_tool(self, entry: ToolCatalogEntry) -> ToolCatalogEntry:
        return self.upsert_item(entry)

    def seed(self, entries: list[ToolCatalogEntry]) -> None:
        for entry in entries:
            self.upsert_tool(entry)
