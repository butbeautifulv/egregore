from __future__ import annotations

import ast
from pathlib import Path

import pytest

DOMAIN_ROOT = Path(__file__).resolve().parents[2] / "cys_core" / "domain"

# Modules still migrating off lazy infra imports (tracked in P3/P6).
ALLOWED_INFRA_IMPORTS = {
    "runs/mode_policy.py",
    "workers/budgets.py",
    "security/classification.py",
    "security/profile_tools.py",
    "security/risk.py",
}


def _collect_infra_imports(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    violations: list[str] = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("cys_core.infrastructure") or alias.name.startswith("cys_core.application"):
                    violations.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("cys_core.infrastructure") or node.module.startswith("cys_core.application"):
                violations.append(node.module)
    if "cys_core.infrastructure" in source or "cys_core.application" in source:
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "cys_core.infrastructure" in stripped or "cys_core.application" in stripped:
                if "import" in stripped or "from" in stripped:
                    pass  # already handled by AST; catches lazy import strings in try blocks
    return violations


@pytest.mark.unit
def test_domain_pure_modules_have_no_infra_imports():
    violations: dict[str, list[str]] = {}
    for path in sorted(DOMAIN_ROOT.rglob("*.py")):
        rel = path.relative_to(DOMAIN_ROOT).as_posix()
        if rel in ALLOWED_INFRA_IMPORTS:
            continue
        found = _collect_infra_imports(path)
        if found:
            violations[rel] = found
    assert not violations, f"domain modules must not import infrastructure/application: {violations}"
