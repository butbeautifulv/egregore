from __future__ import annotations

import pytest

from bootstrap.product_packs import PRODUCT_PACKS, product_pack_to_profile_pack
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID


@pytest.mark.unit
def test_product_pack_registry_lookup() -> None:
    pack = PRODUCT_PACKS[DEFAULT_PROFILE_ID]
    assert pack.profile_id == DEFAULT_PROFILE_ID
    profile = product_pack_to_profile_pack(pack)
    assert "consultant" in profile.default_personas
