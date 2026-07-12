from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import yaml


def test_fga_model_contains_workspace_edit_permission() -> None:
    model = Path("authz/model.fga").read_text(encoding="utf-8")

    assert "type workspace" in model
    assert "define can_edit" in model
    assert "type engagement" in model
    assert "define can_operate" in model


def test_fga_model_yaml_contract() -> None:
    data = yaml.safe_load(Path("authz/model.fga.yaml").read_text(encoding="utf-8"))

    assert data["model_file"] == "model.fga"
    assert data["tuples"]
    assert data["tests"]
    assert any(test.get("list_objects") for test in data["tests"])


def test_fga_model_cli_validate() -> None:
    if shutil.which("fga") is None:
        return
    subprocess.run(
        ["fga", "model", "validate", "--file", "authz/model.fga"],
        check=True,
    )
