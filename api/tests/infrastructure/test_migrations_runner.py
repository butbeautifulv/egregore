from __future__ import annotations

from pathlib import Path

import pytest

from cys_core.infrastructure.migrations.runner import apply_migrations


class _FakeCursor:
    def __init__(self, conn: "_FakeConnection") -> None:
        self._conn = conn
        self._rows: list[tuple[str]] = []

    def fetchall(self) -> list[tuple[str]]:
        return list(self._rows)

    def execute(self, sql: str, params: tuple[str, ...] | None = None) -> None:
        self._conn.run(sql, params or ())


class _FakeConnection:
    def __init__(self) -> None:
        self.applied: list[str] = []

    def execute(self, sql: str, params: tuple[str, ...] | None = None) -> _FakeCursor:
        cursor = _FakeCursor(self)
        cursor.execute(sql, params or ())
        if "SELECT name FROM schema_migrations" in sql:
            cursor._rows = [(name,) for name in self.applied]
        return cursor

    def run(self, sql: str, params: tuple[str, ...]) -> None:
        if "INSERT INTO schema_migrations" in sql:
            self.applied.append(params[0])
        if sql.strip().startswith("CREATE TABLE IF NOT EXISTS worker_jobs"):
            return

    def commit(self) -> None:
        return

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return


@pytest.mark.unit
def test_apply_migrations_idempotent(monkeypatch, tmp_path: Path):
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "001_a.sql").write_text("SELECT 1;", encoding="utf-8")
    (migrations / "002_b.sql").write_text("SELECT 2;", encoding="utf-8")
    fake = _FakeConnection()
    monkeypatch.setattr("cys_core.infrastructure.migrations.runner.psycopg.connect", lambda _url: fake)

    first = apply_migrations("postgresql://test", migrations)
    second = apply_migrations("postgresql://test", migrations)
    assert first == ["001_a.sql", "002_b.sql"]
    assert second == []
