from __future__ import annotations

from pathlib import Path


def find_package_root(start: Path | None = None) -> Path:
    """Return the nearest ancestor directory that contains pyproject.toml.

    Callers should pass their own `Path(__file__)` as `start` if they need
    *their own* package's root — this module (bootstrap.paths) is physically
    duplicated into both backend/api and backend/worker (no shared package
    between them, see docs/MSP_BACKLOG.md §18), so relying on
    the default (this module's own location) only ever resolves to the
    package this copy happens to live in, not necessarily the caller's.
    """
    current = (start or Path(__file__).resolve()).parent
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise RuntimeError("package root (pyproject.toml) not found")


def find_repo_root(start: Path | None = None) -> Path:
    """Return the nearest ancestor directory that is the egregore repo root.

    Walks up looking for `.git`, not "parent of the nearest pyproject.toml" —
    the latter broke once this module became a shared dependency installed
    into multiple sibling packages at different nesting depths; `.git` is
    the one marker that's always correct regardless of which package this
    module happens to be imported from.
    """
    current = (start or Path(__file__).resolve()).parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    raise RuntimeError("repo root (.git) not found")
