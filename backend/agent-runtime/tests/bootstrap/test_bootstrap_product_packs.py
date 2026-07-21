from __future__ import annotations

import pytest

from bootstrap.product_packs import (
    CYBERSEC_SOC_PRODUCT,
    GAIA_BENCHMARK_PRODUCT,
    GENERAL_ASSISTANT_PRODUCT,
    PRODUCT_PACKS,
)


@pytest.mark.unit
def test_product_packs_registry() -> None:
    assert set(PRODUCT_PACKS) == {"cybersec-soc", "general-assistant", "gaia-benchmark"}
    assert CYBERSEC_SOC_PRODUCT.profile_id == "cybersec-soc"
    assert GENERAL_ASSISTANT_PRODUCT.personas[0].catalog_agent == "consultant"
    assert GAIA_BENCHMARK_PRODUCT.eval_pack is not None
    assert GAIA_BENCHMARK_PRODUCT.eval_pack.suite == "gaia"
    assert set(CYBERSEC_SOC_PRODUCT.tool_domains) == {"veil", "siem", "nessus"}
    assert GENERAL_ASSISTANT_PRODUCT.tool_domains == []
    assert GAIA_BENCHMARK_PRODUCT.tool_domains == []
