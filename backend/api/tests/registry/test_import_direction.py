from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
# registry/agents.py moved into the shared `contracts` package during
# task #38's api/worker split (docs/MICROSERVICES_SPLIT_PLAN.md) — it's no
# longer under this project's own src/.
CONTRACTS_ROOT = ROOT.parent / "contracts"


@pytest.mark.unit
def test_registry_agents_no_bootstrap_product_loader():
    text = (CONTRACTS_ROOT / "src" / "cys_core" / "registry" / "agents.py").read_text(encoding="utf-8")
    assert "from bootstrap.product_loader" not in text
