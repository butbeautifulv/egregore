from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _stub_catalog_hints_for_run_step(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("cys_core.application.plans_as_hints.load_plan_hints", lambda plans_dir=None: [])
    monkeypatch.setattr("cys_core.application.skills.catalog.list_skill_metadata", lambda profile_id="": [])
