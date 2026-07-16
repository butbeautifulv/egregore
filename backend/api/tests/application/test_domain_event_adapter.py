from __future__ import annotations

import pytest

from bootstrap.product_packs import CYBERSEC_SOC_PRODUCT
from cys_core.application.routing.domain_event_adapter import resolve_domain_for_profile
from cys_core.infrastructure.bootstrap.product_pack_adapter import build_product_pack_port


@pytest.mark.unit
def test_resolve_domain_for_cybersec_profile() -> None:
    packs = build_product_pack_port()
    assert resolve_domain_for_profile(CYBERSEC_SOC_PRODUCT.profile_id, packs=packs) == "cybersecurity"
