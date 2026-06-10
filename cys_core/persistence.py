from __future__ import annotations

from contextlib import AbstractContextManager
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


_persistence: PersistenceStack | None = None


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
