#!/usr/bin/env python3
"""Architecture audit: cross-layer import violations and baseline snapshot."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_IN_DOMAIN = {
    "cys_core.infrastructure",
    "cys_core.registry",
    "cys_core.runtime",
    "cys_core.middleware",
    "cys_core.security",
    "cys_core.observability",
    "cys_core.llm",
    "cys_core.persistence",
    "bootstrap",
    "interfaces",
}

FORBIDDEN_IN_APPLICATION = FORBIDDEN_IN_DOMAIN | {"cys_core.infrastructure"}


def _module_name(path: Path) -> str:
    rel = path.relative_to(ROOT).with_suffix("")
    return ".".join(rel.parts)


def _imports_in_file(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def _violations_for_prefix(prefix: str, forbidden: set[str]) -> list[dict[str, str]]:
    base = ROOT / prefix.replace(".", "/")
    if not base.exists():
        return []
    hits: list[dict[str, str]] = []
    for path in base.rglob("*.py"):
        mod = _module_name(path)
        for imp in _imports_in_file(path):
            root = imp.split(".")[0] if imp else ""
            full = imp
            if any(full == f or full.startswith(f + ".") for f in forbidden):
                hits.append({"module": mod, "imports": imp})
            elif root in {"bootstrap", "interfaces"}:
                hits.append({"module": mod, "imports": imp})
    return hits


def audit() -> dict:
    return {
        "domain_violations": _violations_for_prefix("cys_core/domain", FORBIDDEN_IN_DOMAIN),
        "application_violations": _violations_for_prefix("cys_core/application", FORBIDDEN_IN_APPLICATION),
    }


def main() -> int:
    report = audit()
    out = ROOT / "docs" / "refactor_baseline.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    total = len(report["domain_violations"]) + len(report["application_violations"])
    print(json.dumps(report, indent=2))
    if total:
        print(f"arch_audit: {total} known cross-layer imports (baseline)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
