from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Generic, TypeVar, cast

import psycopg
from pydantic import BaseModel

from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.infrastructure.catalog.schema import CATALOG_SCHEMA_SQL
from cys_core.infrastructure.postgres_retry import connect_with_retry

T = TypeVar("T", bound=BaseModel)


class PostgresJsonCatalog(Generic[T]):
    """Shared Postgres JSONB catalog pattern for secondary registries."""

    def __init__(
        self,
        postgres_url: str,
        *,
        table: str,
        model_class: type[T],
        order_by: str = "id",
    ) -> None:
        self._postgres_url = postgres_url
        self._table = table
        self._model_class = model_class
        self._order_by = order_by
        with psycopg.connect(self._postgres_url) as conn:
            conn.execute(CATALOG_SCHEMA_SQL)
            conn.commit()

    def _connect(self) -> psycopg.Connection:
        return connect_with_retry(self._postgres_url)

    def list_items(
        self, *, profile_id: str | None = None, enabled_only: bool = True
    ) -> list[T]:
        clauses = ["1=1"]
        params: list[object] = []
        if profile_id:
            clauses.append("profile_id = %s")
            params.append(profile_id)
        if enabled_only:
            clauses.append("enabled = TRUE")
        sql = f"SELECT payload FROM {self._table} WHERE {' AND '.join(clauses)} ORDER BY {self._order_by}"
        with self._connect() as conn:
            rows = conn.execute(cast(Any, sql), params).fetchall()
        return [self._model_class.model_validate(row[0]) for row in rows]

    def get_item(self, item_id: str, *, profile_id: str = DEFAULT_PROFILE_ID) -> T | None:
        with self._connect() as conn:
            row = conn.execute(
                cast(Any, f"SELECT payload FROM {self._table} WHERE id = %s AND profile_id = %s"),
                (item_id, profile_id),
            ).fetchone()
        if row is None:
            return None
        return self._model_class.model_validate(row[0])

    def upsert_item(
        self,
        entry: T,
        *,
        merge: Callable[[T, T], None] | None = None,
        versioned: bool = False,
        extra_columns: tuple[str, ...] = (),
    ) -> T:
        item_id = getattr(entry, "id")
        profile_id = getattr(entry, "profile_id")
        if merge is not None:
            existing = self.get_item(item_id, profile_id=profile_id)
            if existing is not None:
                merge(entry, existing)
        payload = entry.model_dump(mode="json")
        columns = ["id", "profile_id", "payload"]
        values: list[object] = [item_id, profile_id, json.dumps(payload)]
        update_sets = ["payload = EXCLUDED.payload"]
        if versioned:
            columns.append("version")
            values.append(getattr(entry, "version"))
            update_sets.append("version = EXCLUDED.version")
        for col in extra_columns:
            columns.append(col)
            values.append(getattr(entry, col))
            update_sets.append(f"{col} = EXCLUDED.{col}")
        columns.append("enabled")
        values.append(getattr(entry, "enabled"))
        update_sets.append("enabled = EXCLUDED.enabled")
        update_sets.append("updated_at = NOW()")
        cols = ", ".join(columns)
        placeholders = ", ".join(["%s"] * len(values))
        conflict_updates = ", ".join(update_sets)
        sql = f"""
            INSERT INTO {self._table} ({cols}, updated_at)
            VALUES ({placeholders}, NOW())
            ON CONFLICT (id, profile_id) DO UPDATE SET {conflict_updates}
        """
        with self._connect() as conn:
            conn.execute(cast(Any, sql), cast(Any, values))
            conn.commit()
        return entry
