from __future__ import annotations

from typing import Protocol

from cys_core.domain.catalog.product_packs import ProductProfilePack


class ProductPackPort(Protocol):
    def get_pack(self, profile_id: str) -> ProductProfilePack | None: ...

    def default_domain_for_profile(self, profile_id: str) -> str: ...
