from pathlib import Path

import pytest

from cys_core.application.plans.plan_loader import load_plan_routing, load_plans_from_dir
from cys_core.domain.events.plans import severity_at_least
from cys_core.registry.product_context import default_agents_root


@pytest.mark.unit
def test_load_plans_from_agents_dir():
    plans = load_plans_from_dir(default_agents_root() / "plans")
    ids = {p.id for p in plans}
    assert "incident-triage" in ids
    assert any(p.rules for p in plans)


@pytest.mark.unit
def test_load_plan_routing_enqueue_alias(tmp_path: Path):
    path = tmp_path / "p.yaml"
    path.write_text(
        """
id: test
rules:
  - when:
      event_types: [doc.upload]
    enqueue: compliance
""",
        encoding="utf-8",
    )
    plan = load_plan_routing(path)
    assert plan.rules[0].personas == ["compliance"]


@pytest.mark.unit
def test_severity_at_least_equal():
    assert severity_at_least("medium", "medium")


@pytest.mark.unit
def test_load_plans_from_missing_dir(tmp_path: Path):
    assert load_plans_from_dir(tmp_path / "missing") == []
