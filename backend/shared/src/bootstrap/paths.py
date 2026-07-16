from __future__ import annotations

from pathlib import Path


def find_api_root(start: Path | None = None) -> Path:
    """Return the nearest ancestor directory that contains pyproject.toml (api/)."""
    current = (start or Path(__file__).resolve()).parent
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise RuntimeError("api root (pyproject.toml) not found")


def find_repo_root(start: Path | None = None) -> Path:
    """Parent of api/ (egregore product repo root)."""
    return find_api_root(start).parent
