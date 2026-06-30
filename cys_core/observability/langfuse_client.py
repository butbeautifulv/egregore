from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from bootstrap.settings import settings

logger = logging.getLogger(__name__)


@lru_cache
def _ensure_langfuse_client() -> bool:
    """Initialize Langfuse SDK once when both API keys are configured."""
    if not settings.langfuse_enabled:
        return False
    try:
        from langfuse import Langfuse

        Langfuse(
            public_key=settings.resolved_langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.resolved_langfuse_host,
        )
        return True
    except Exception:
        logger.warning("Failed to initialize Langfuse client", exc_info=True)
        return False


def get_langfuse_callback_handler() -> Any | None:
    """Return LangChain CallbackHandler when Langfuse tracing is enabled."""
    if not _ensure_langfuse_client():
        return None
    try:
        from langfuse.langchain import CallbackHandler

        return CallbackHandler()
    except Exception:
        logger.warning("Failed to create Langfuse CallbackHandler", exc_info=True)
        return None


def flush_langfuse() -> None:
    """Flush pending Langfuse events (required for short-lived CLI worker runs)."""
    if not settings.langfuse_enabled:
        return
    try:
        from langfuse import get_client

        get_client().flush()
    except Exception:
        logger.warning("Failed to flush Langfuse client", exc_info=True)


def shutdown_langfuse() -> None:
    """Flush and shut down the Langfuse client (API lifespan / graceful exit)."""
    if not settings.langfuse_enabled:
        return
    try:
        from langfuse import get_client

        client = get_client()
        client.flush()
        client.shutdown()
    except Exception:
        logger.warning("Failed to shutdown Langfuse client", exc_info=True)


def reset_langfuse_client_cache() -> None:
    """Clear cached client init state (tests only)."""
    _ensure_langfuse_client.cache_clear()
