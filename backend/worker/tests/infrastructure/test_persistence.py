from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest


@pytest.mark.unit
def test_persistence_memory_postgres_fallback_and_singleton(monkeypatch):
    import cys_core.persistence as persistence

    stack = persistence.PersistenceStack(force_memory=True)
    assert stack._use_memory() is True
    with stack as active:
        assert active.checkpointer is not None
        assert active.store is not None

    monkeypatch.setattr(persistence.settings, "use_memory_fallback", False)
    monkeypatch.setattr(persistence.settings, "stage", "dev")
    assert persistence.PersistenceStack(force_memory=False)._use_memory() is False

    class FakeResource:
        def __init__(self):
            self.setup_called = False

        def setup(self):
            self.setup_called = True

    class FakeContextManager:
        def __init__(self, resource):
            self.resource = resource
            self.exited = False

        def __enter__(self):
            return self.resource

        def __exit__(self, exc_type, exc, tb):
            self.exited = True

    checkpoint = FakeResource()
    store = FakeResource()
    checkpoint_cm = FakeContextManager(checkpoint)
    store_cm = FakeContextManager(store)
    checkpoint_module = types.ModuleType("langgraph.checkpoint.postgres")
    store_module = types.ModuleType("langgraph.store.postgres")
    checkpoint_module.PostgresSaver = SimpleNamespace(from_conn_string=lambda _url: checkpoint_cm)
    store_module.PostgresStore = SimpleNamespace(from_conn_string=lambda _url: store_cm)
    monkeypatch.setitem(sys.modules, "langgraph.checkpoint.postgres", checkpoint_module)
    monkeypatch.setitem(sys.modules, "langgraph.store.postgres", store_module)

    postgres_stack = persistence.PersistenceStack(force_memory=False)
    postgres_stack.__enter__()
    assert checkpoint.setup_called is True
    assert store.setup_called is True
    postgres_stack.__exit__(None, None, None)
    assert checkpoint_cm.exited is True
    assert store_cm.exited is True

    def _raise_db_error(_url: str) -> None:
        raise RuntimeError("db")

    checkpoint_module.PostgresSaver = SimpleNamespace(from_conn_string=_raise_db_error)
    fallback_stack = persistence.PersistenceStack(force_memory=False).__enter__()
    assert fallback_stack.checkpointer is not None
    assert fallback_stack.store is not None

    monkeypatch.setattr(persistence, "_persistence", None)
    forced = persistence.get_persistence(force_memory=True)
    cached = persistence.get_persistence()
    assert forced is not cached
    assert persistence.get_persistence() is cached

    assert persistence.get_persistence_connector("auto").name == "auto"
    assert persistence.get_persistence_connector("auto").open(force_memory=True).checkpointer is not None
    assert persistence.get_persistence_connector("memory").open().checkpointer is not None
    assert persistence.get_persistence_connector("postgres").name == "postgres"
    assert persistence.get_persistence_connector("postgres").open().checkpointer is not None
    monkeypatch.setattr(persistence.settings, "persistence_connector", "memory")
    assert persistence.get_persistence_connector().name == "memory"
    with pytest.raises(ValueError, match="Unknown persistence connector"):
        persistence.get_persistence_connector("missing")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_persistence_memory_postgres_fallback_and_singleton(monkeypatch):
    import cys_core.persistence as persistence

    stack = persistence.AsyncPersistenceStack(force_memory=True)
    assert stack._use_memory() is True
    async with stack as active:
        assert active.checkpointer is not None
        assert active.store is not None

    monkeypatch.setattr(persistence.settings, "use_memory_fallback", False)
    monkeypatch.setattr(persistence.settings, "stage", "dev")
    assert persistence.AsyncPersistenceStack(force_memory=False)._use_memory() is False

    class FakeAsyncResource:
        def __init__(self):
            self.setup_called = False

        async def setup(self):
            self.setup_called = True

    class FakeAsyncContextManager:
        def __init__(self, resource):
            self.resource = resource
            self.exited = False

        async def __aenter__(self):
            return self.resource

        async def __aexit__(self, exc_type, exc, tb):
            self.exited = True

    checkpoint = FakeAsyncResource()
    store = FakeAsyncResource()
    checkpoint_cm = FakeAsyncContextManager(checkpoint)
    store_cm = FakeAsyncContextManager(store)
    checkpoint_module = types.ModuleType("langgraph.checkpoint.postgres.aio")
    store_module = types.ModuleType("langgraph.store.postgres.aio")
    checkpoint_module.AsyncPostgresSaver = SimpleNamespace(from_conn_string=lambda _url: checkpoint_cm)
    store_module.AsyncPostgresStore = SimpleNamespace(from_conn_string=lambda _url: store_cm)
    monkeypatch.setitem(sys.modules, "langgraph.checkpoint.postgres.aio", checkpoint_module)
    monkeypatch.setitem(sys.modules, "langgraph.store.postgres.aio", store_module)

    postgres_stack = persistence.AsyncPersistenceStack(force_memory=False)
    await postgres_stack.__aenter__()
    assert checkpoint.setup_called is True
    assert store.setup_called is True
    await postgres_stack.__aexit__(None, None, None)
    assert checkpoint_cm.exited is True
    assert store_cm.exited is True

    checkpoint_module.AsyncPostgresSaver = SimpleNamespace(
        from_conn_string=lambda _url: (_ for _ in ()).throw(RuntimeError("db"))
    )
    fallback_stack = await persistence.AsyncPersistenceStack(force_memory=False).__aenter__()
    assert fallback_stack.checkpointer is not None
    assert fallback_stack.store is not None

    monkeypatch.setattr(persistence, "_async_persistence", None)
    forced = await persistence.get_async_persistence(force_memory=True)
    cached = await persistence.get_async_persistence()
    assert forced is not cached
    assert await persistence.get_async_persistence() is cached
    assert (await persistence.get_persistence_connector("memory").open_async()).store is not None
