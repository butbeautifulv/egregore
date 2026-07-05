from __future__ import annotations

import importlib
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PORTS = ROOT / "cys_core" / "application" / "ports"


def _rg(pattern: str, path: Path) -> list[str]:
    result = subprocess.run(
        ["rg", "-n", pattern, str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode == 1:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


@pytest.mark.unit
def test_ports_barrel_imports():
    import cys_core.application.ports as ports

    for name in ports.__all__:
        assert hasattr(ports, name), f"missing export: {name}"


@pytest.mark.unit
def test_ports_modules_import_individually():
    skip = {"__init__.py", "__pycache__"}
    for path in sorted(PORTS.rglob("*.py")):
        if path.name in skip or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(PORTS).with_suffix("")
        module_name = "cys_core.application.ports." + ".".join(rel.parts)
        importlib.import_module(module_name)


@pytest.mark.unit
def test_ports_no_forbidden_layer_imports():
    forbidden = _rg(
        r"from (cys_core\.infrastructure\.|bootstrap\.|interfaces\.)",
        PORTS,
    )
    assert forbidden == [], "ports must not import infrastructure/bootstrap/interfaces:\n" + "\n".join(
        forbidden
    )
