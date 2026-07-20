from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import scripts.verify_import_boundaries as boundaries

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
def test_domain_no_application_bootstrap_interfaces_imports():
    assert boundaries.check_domain_no_application_bootstrap_interfaces() == []


@pytest.mark.unit
def test_application_no_bootstrap_interfaces_imports():
    assert boundaries.check_application_no_bootstrap_interfaces() == []


@pytest.mark.unit
def test_verify_no_langfuse_in_core_script():
    script = ROOT / "scripts" / "verify_no_langfuse_in_core.sh"
    result = subprocess.run(["bash", str(script)], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.unit
def test_verify_import_boundaries_script():
    script = ROOT / "scripts" / "verify_import_boundaries.py"
    result = subprocess.run(["uv", "run", "python", str(script)], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Architecture import boundary summary:" in result.stdout
    assert "OK application -> bootstrap/interfaces" in result.stdout
