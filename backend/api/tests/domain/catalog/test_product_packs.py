from __future__ import annotations

import pytest

from cys_core.domain.catalog.product_packs import (
    DomainPack,
    EvalPack,
    PersonaPack,
    ProductProfilePack,
)
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID


@pytest.mark.unit
def test_product_profile_pack_round_trip() -> None:
    from bootstrap.product_packs import product_pack_to_profile_pack

    pack = ProductProfilePack(
        id="cybersec-soc",
        name="Cybersec SOC",
        profile_id=DEFAULT_PROFILE_ID,
        domains=[
            DomainPack(
                id="cybersecurity",
                name="Cybersecurity",
                default_plan="incident-triage",
                routing_event_types=["siem.alert", "engagement.start"],
            )
        ],
        personas=[
            PersonaPack(id="consultant", name="Consultant", catalog_agent="consultant"),
            PersonaPack(id="soc", name="SOC", catalog_agent="soc"),
        ],
        eval_pack=EvalPack(id="soc-eval", suite="trace-critic", metrics=["faithfulness"]),
    )
    profile = product_pack_to_profile_pack(pack)
    assert profile.id == DEFAULT_PROFILE_ID
    assert "consultant" in profile.default_personas
    assert pack.domains[0].default_plan == "incident-triage"
