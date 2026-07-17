from __future__ import annotations

import pytest

from cys_core.domain.catalog.models import AgentCatalogEntry
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID, resolve_profile_id


@pytest.mark.unit
def test_resolve_profile_id_explicit_wins():
    assert (
        resolve_profile_id(
            explicit="custom-profile",
            payload={"profile_id": "payload-profile"},
            catalog_entry=AgentCatalogEntry(name="soc", profile_id="catalog-profile"),
        )
        == "custom-profile"
    )


@pytest.mark.unit
def test_resolve_profile_id_payload_over_catalog():
    assert (
        resolve_profile_id(
            payload={"profile_id": "payload-profile"},
            catalog_entry=AgentCatalogEntry(name="soc", profile_id="catalog-profile"),
        )
        == "payload-profile"
    )


@pytest.mark.unit
def test_resolve_profile_id_catalog_entry():
    assert (
        resolve_profile_id(
            catalog_entry=AgentCatalogEntry(name="soc", profile_id="catalog-profile"),
        )
        == "catalog-profile"
    )


@pytest.mark.unit
def test_resolve_profile_id_default():
    assert resolve_profile_id() == DEFAULT_PROFILE_ID
    assert resolve_profile_id(payload={}) == DEFAULT_PROFILE_ID
    assert resolve_profile_id(catalog_entry=AgentCatalogEntry(name="soc", profile_id="")) == DEFAULT_PROFILE_ID
