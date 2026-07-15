from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
def test_registry_agents_no_bootstrap_product_loader():
    text = (ROOT / "cys_core" / "registry" / "agents.py").read_text(encoding="utf-8")
    assert "from bootstrap.product_loader" not in text
