from __future__ import annotations


class PersistenceUnavailableError(RuntimeError):
    """Raised when durable persistence is required but unavailable."""
