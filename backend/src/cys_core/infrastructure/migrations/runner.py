from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import psycopg

_DEFAULT_MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"


def apply_migrations(postgres_url: str, migrations_dir: Path | None = None) -> list[str]:
    """Apply SQL migrations in lexical order; returns newly applied migration names."""
    root = migrations_dir or _DEFAULT_MIGRATIONS_DIR
    files = sorted(root.glob("*.sql"))
    applied: list[str] = []
    with psycopg.connect(postgres_url) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                name TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.commit()
        existing = {
            row[0]
            for row in conn.execute("SELECT name FROM schema_migrations").fetchall()
        }
        for path in files:
            if path.name in existing:
                continue
            sql = path.read_text(encoding="utf-8")
            conn.execute(cast(Any, sql))
            conn.execute(cast(Any, "INSERT INTO schema_migrations (name) VALUES (%s)"), (path.name,))
            conn.commit()
            applied.append(path.name)
    return applied
