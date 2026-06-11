from __future__ import annotations

import inspect
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from typing import Self

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore

from config import settings


class PersistenceStack(AbstractContextManager["PersistenceStack"]):
    """Manages Postgres or in-memory checkpointer and store."""

    def __init__(self, force_memory: bool | None = None) -> None:
        self._force_memory = force_memory
        self._checkpointer_cm = None
        self._store_cm = None
        self.checkpointer: BaseCheckpointSaver | None = None
        self.store: BaseStore | None = None

    def _use_memory(self) -> bool:
        if self._force_memory is not None:
            return self._force_memory
        return settings.use_memory_fallback or settings.stage == "test"

    def __enter__(self) -> Self:
        if self._use_memory():
            self.checkpointer = MemorySaver()
            self.store = InMemoryStore()
            return self

        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            from langgraph.store.postgres import PostgresStore

            self._checkpointer_cm = PostgresSaver.from_conn_string(settings.postgres_url)
            self.checkpointer = self._checkpointer_cm.__enter__()
            self.checkpointer.setup()

            self._store_cm = PostgresStore.from_conn_string(settings.postgres_url)
            self.store = self._store_cm.__enter__()
            self.store.setup()
        except Exception:
            self.checkpointer = MemorySaver()
            self.store = InMemoryStore()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._store_cm is not None:
            self._store_cm.__exit__(exc_type, exc, tb)
        if self._checkpointer_cm is not None:
            self._checkpointer_cm.__exit__(exc_type, exc, tb)


class AsyncPersistenceStack(AbstractAsyncContextManager["AsyncPersistenceStack"]):
    """Async Postgres or in-memory checkpointer and store."""

    def __init__(self, force_memory: bool | None = None) -> None:
        self._force_memory = force_memory
        self._checkpointer_cm = None
        self._store_cm = None
        self.checkpointer: BaseCheckpointSaver | None = None
        self.store: BaseStore | None = None

    def _use_memory(self) -> bool:
        if self._force_memory is not None:
            return self._force_memory
        return settings.use_memory_fallback or settings.stage == "test"

    async def __aenter__(self) -> Self:
        if self._use_memory():
            self.checkpointer = MemorySaver()
            self.store = InMemoryStore()
            return self

        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from langgraph.store.postgres.aio import AsyncPostgresStore

            self._checkpointer_cm = AsyncPostgresSaver.from_conn_string(settings.postgres_url)
            self.checkpointer = await self._checkpointer_cm.__aenter__()
            maybe_setup = self.checkpointer.setup()
            if inspect.isawaitable(maybe_setup):
                await maybe_setup

            self._store_cm = AsyncPostgresStore.from_conn_string(settings.postgres_url)
            self.store = await self._store_cm.__aenter__()
            maybe_store_setup = self.store.setup()
            if inspect.isawaitable(maybe_store_setup):
                await maybe_store_setup
        except Exception:
            self.checkpointer = MemorySaver()
            self.store = InMemoryStore()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._store_cm is not None:
            await self._store_cm.__aexit__(exc_type, exc, tb)
        if self._checkpointer_cm is not None:
            await self._checkpointer_cm.__aexit__(exc_type, exc, tb)


_persistence: PersistenceStack | None = None
_async_persistence: AsyncPersistenceStack | None = None


def get_persistence(force_memory: bool | None = None) -> PersistenceStack:
    """Return active persistence stack (singleton unless force_memory set)."""
    global _persistence
    if force_memory is not None or _persistence is None:
        stack = PersistenceStack(force_memory=force_memory)
        stack.__enter__()
        if force_memory is None:
            _persistence = stack
        return stack
    return _persistence


async def get_async_persistence(force_memory: bool | None = None) -> AsyncPersistenceStack:
    """Return active async persistence stack (singleton unless force_memory set)."""
    global _async_persistence
    if force_memory is not None or _async_persistence is None:
        stack = AsyncPersistenceStack(force_memory=force_memory)
        await stack.__aenter__()
        if force_memory is None:
            _async_persistence = stack
        return stack
    return _async_persistence
