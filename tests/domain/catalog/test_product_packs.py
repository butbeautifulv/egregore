from __future__ import annotations

from cys_core.domain.catalog.models import ProfilePack
from cys_core.domain.catalog.product_packs import DomainPack, EvalPack, PersonaPack, ProductProfilePack


def test_product_profile_pack_roundtrip() -> None:
    pack = ProductProfilePack(
        id="general",
        name="General Assistant",
        profiles=[ProfilePack(id="general", name="General", default_personas=["consultant"])],
        domains=[DomainPack(id="general", name="General")],
        personas=[PersonaPack(id="default", personas=["consultant"])],
        evals=[EvalPack(id="smoke", suites=["tiny-smoke"])],
        default_profile_id="general",
    )

    dumped = pack.model_dump(mode="json")
    loaded = ProductProfilePack.model_validate(dumped)
    assert loaded.resolve_default_profile_id() == "general"
    assert loaded.profiles[0].default_personas == ["consultant"]

