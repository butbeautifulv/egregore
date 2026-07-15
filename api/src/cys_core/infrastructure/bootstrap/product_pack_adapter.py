from __future__ import annotations

from bootstrap import product_packs as _product_packs
from cys_core.application.ports.product_pack import ProductPackPort
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID


class BootstrapProductPackAdapter:
    def get_pack(self, profile_id: str):
        return _product_packs.PRODUCT_PACKS.get(profile_id)

    def default_domain_for_profile(self, profile_id: str) -> str:
        pack = self.get_pack(profile_id)
        if pack is not None and pack.domains:
            return pack.domains[0].id
        if profile_id == DEFAULT_PROFILE_ID:
            return "cybersecurity"
        return "general"


def build_product_pack_port() -> ProductPackPort:
    return BootstrapProductPackAdapter()
