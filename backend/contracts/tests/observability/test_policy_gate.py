from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from scripts.check_agent_policy_tests import check_policy_tests_updated


@pytest.mark.unit
def test_policy_gate_passes_without_agent_changes():
    repo = Path(__file__).resolve().parents[2]
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    assert check_policy_tests_updated(head, head) == 0
