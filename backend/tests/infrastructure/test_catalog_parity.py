from __future__ import annotations

import os

import pytest

from cys_core.domain.catalog.models import SkillCatalogEntry, StagingStatus
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.infrastructure.catalog.memory_skills import InMemorySkillCatalog
from cys_core.infrastructure.catalog.registry_factory import reset_catalog_singletons


def _sample_skill(skill_id: str = "test-skill") -> SkillCatalogEntry:
    return SkillCatalogEntry(
        id=skill_id,
        name=skill_id,
        description="parity test",
        body="# skill body",
        profile_id=DEFAULT_PROFILE_ID,
        trust_tier="community",
        staging_status=StagingStatus.DRAFT,
    )


def test_memory_skill_catalog_roundtrip():
    catalog = InMemorySkillCatalog()
    entry = _sample_skill()
    saved = catalog.upsert_skill(entry)
    assert saved.version == 1
    fetched = catalog.get_skill(entry.id, profile_id=DEFAULT_PROFILE_ID)
    assert fetched is not None
    assert fetched.description == "parity test"
    listed = catalog.list_skills(profile_id=DEFAULT_PROFILE_ID, enabled_only=False)
    assert len(listed) == 1
    catalog.delete_skill(entry.id, profile_id=DEFAULT_PROFILE_ID)
    disabled = catalog.get_skill(entry.id, profile_id=DEFAULT_PROFILE_ID)
    assert disabled is not None
    assert disabled.enabled is False


@pytest.mark.skipif(not os.environ.get("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL not set")
def test_postgres_skill_catalog_roundtrip():
    psycopg = pytest.importorskip("psycopg")
    del psycopg
    from cys_core.infrastructure.catalog.postgres_registry import PostgresSkillCatalog

    reset_catalog_singletons()
    catalog = PostgresSkillCatalog(os.environ["TEST_POSTGRES_URL"])
    entry = _sample_skill("pg-skill")
    saved = catalog.upsert_skill(entry)
    assert saved.version == 1
    fetched = catalog.get_skill(entry.id, profile_id=DEFAULT_PROFILE_ID)
    assert fetched is not None
    assert fetched.body == "# skill body"
    updated = _sample_skill("pg-skill")
    updated.description = "updated"
    saved2 = catalog.upsert_skill(updated)
    assert saved2.version == 2
