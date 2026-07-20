from __future__ import annotations

import pytest

from cys_core.application.ports.reflexion import ReflexionLesson
from cys_core.domain.memory.models import MemoryEntry, MemoryScope
from cys_core.infrastructure.memory.stores import InMemoryEpisodicMemoryStore
from cys_core.infrastructure.reflexion.memory import EpisodicReflexionStore, InMemoryReflexionStore


@pytest.mark.unit
def test_episodic_reflexion_store_roundtrips_a_lesson():
    # _sanitize_lesson wraps content in USER_DATA_TO_PROCESS markers before storing (existing
    # InputSanitizer.sanitize behavior, unchanged by this adapter) — assert containment, not
    # raw equality, same as the pre-existing InMemoryReflexionStore would round-trip it.
    episodic = InMemoryEpisodicMemoryStore()
    store = EpisodicReflexionStore(episodic)
    store.append(ReflexionLesson(investigation_id="inv-1", tenant_id="t1", lesson="always cite obs_id"))
    results = store.list_for_investigation("t1", "inv-1")
    assert len(results) == 1
    assert "always cite obs_id" in results[0]


@pytest.mark.unit
def test_episodic_reflexion_store_survives_a_fresh_adapter_over_the_same_backend():
    """The whole point of this change: a lesson written by one adapter instance (e.g. one
    process) must be readable by a different adapter instance wrapping the same durable
    backend — proving persistence isn't tied to the adapter's own lifetime, unlike the old
    bare InMemoryReflexionStore where a fresh process meant an empty list."""
    episodic = InMemoryEpisodicMemoryStore()
    EpisodicReflexionStore(episodic).append(
        ReflexionLesson(investigation_id="inv-1", tenant_id="t1", lesson="lesson one")
    )
    fresh = EpisodicReflexionStore(episodic)
    results = fresh.list_for_investigation("t1", "inv-1")
    assert len(results) == 1
    assert "lesson one" in results[0]


@pytest.mark.unit
def test_episodic_reflexion_store_filters_out_non_lesson_entries():
    episodic = InMemoryEpisodicMemoryStore()
    scope = MemoryScope(tenant_id="t1", investigation_id="inv-1")
    episodic.append(MemoryEntry(scope=scope, content="a finding, not a lesson", memory_type="finding"))
    store = EpisodicReflexionStore(episodic)
    store.append(ReflexionLesson(investigation_id="inv-1", tenant_id="t1", lesson="the real lesson"))
    results = store.list_for_investigation("t1", "inv-1")
    assert len(results) == 1
    assert "the real lesson" in results[0]


@pytest.mark.unit
def test_episodic_reflexion_store_respects_tenant_and_investigation_scope():
    episodic = InMemoryEpisodicMemoryStore()
    store = EpisodicReflexionStore(episodic)
    store.append(ReflexionLesson(investigation_id="inv-1", tenant_id="t1", lesson="t1 lesson"))
    store.append(ReflexionLesson(investigation_id="inv-2", tenant_id="t1", lesson="other investigation"))
    store.append(ReflexionLesson(investigation_id="inv-1", tenant_id="t2", lesson="other tenant"))
    results = store.list_for_investigation("t1", "inv-1")
    assert len(results) == 1
    assert "t1 lesson" in results[0]


@pytest.mark.unit
def test_episodic_reflexion_store_respects_limit():
    episodic = InMemoryEpisodicMemoryStore()
    store = EpisodicReflexionStore(episodic)
    for i in range(10):
        store.append(ReflexionLesson(investigation_id="inv-1", tenant_id="t1", lesson=f"lesson-{i}"))
    assert len(store.list_for_investigation("t1", "inv-1", limit=3)) == 3


@pytest.mark.unit
def test_get_reflexion_store_defaults_to_in_memory_fallback():
    import cys_core.infrastructure.reflexion.memory as reflexion_memory

    reflexion_memory._store = None
    try:
        assert isinstance(reflexion_memory.get_reflexion_store(), InMemoryReflexionStore)
    finally:
        reflexion_memory._store = None
