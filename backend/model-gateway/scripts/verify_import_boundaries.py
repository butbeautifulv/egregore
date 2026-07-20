from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "src" / "cys_core"
APPLICATION = CORE / "application"
DOMAIN = CORE / "domain"

# Scoped-down port of worker/tool-gateway's scripts/verify_import_boundaries.py
# (docs/MSP_BACKLOG.md §56.7) — model-gateway only has domain/application/bootstrap/
# interfaces, none of the other packages' infrastructure/registry/runtime/middleware/
# observability/llm/persistence layers, so only the checks that map to a real layer
# here are ported; import-linter's own contracts (pyproject.toml [tool.importlinter])
# cover the same ground declaratively — this script exists for the same reason the
# other packages keep both: a plain-Python check that's easy to read a failing diff
# from, run standalone with no import-linter config parsing involved.


def _imports_in_file(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def _scan_layer(root: Path, *, prefixes: tuple[str, ...]) -> list[str]:
    violations: list[str] = []
    if not root.exists():
        return violations
    for path in root.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        for mod in _imports_in_file(path):
            if mod.startswith(prefixes):
                violations.append(f"{rel}: {mod}")
    return violations


def check_domain_no_application_bootstrap_interfaces() -> list[str]:
    return _scan_layer(DOMAIN, prefixes=("cys_core.application.", "bootstrap.", "interfaces."))


def check_application_no_bootstrap_interfaces() -> list[str]:
    return _scan_layer(APPLICATION, prefixes=("bootstrap.", "interfaces."))


def _print_bucket(name: str, violations: list[str]) -> bool:
    if violations:
        print(f"FAIL {name}:")
        for line in sorted(violations):
            print(f"  {line}")
        return False
    print(f"OK {name}")
    return True


def main() -> int:
    checks = [
        ("domain -> application/bootstrap/interfaces", check_domain_no_application_bootstrap_interfaces()),
        ("application -> bootstrap/interfaces", check_application_no_bootstrap_interfaces()),
    ]
    ok = True
    print("Architecture import boundary summary:")
    for name, violations in checks:
        if not _print_bucket(name, violations):
            ok = False
    if not ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
