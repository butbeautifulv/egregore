from __future__ import annotations

import logging
import threading
import time
from typing import Any

from bootstrap.settings import settings

logger = logging.getLogger(__name__)

_active_spans: dict[str, Any] = {}
_spans_lock = threading.Lock()
_langfuse_init_ok: bool | None = None
_langfuse_init_lock = threading.Lock()


def _ensure_langfuse_client() -> bool:
    global _langfuse_init_ok
    if not settings.langfuse_enabled:
        return False
    with _langfuse_init_lock:
        if _langfuse_init_ok is True:
            return True
        if _langfuse_init_ok is False:
            return False
        try:
            from langfuse import Langfuse

            Langfuse(
                public_key=settings.resolved_langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.resolved_langfuse_host,
            )
            _langfuse_init_ok = True
            return True
        except Exception:
            logger.warning("Failed to initialize Langfuse client", exc_info=True)
            _langfuse_init_ok = False
            return False


def reset_langfuse_client_cache() -> None:
    """Allow retry after transient Langfuse startup failures."""
    global _langfuse_init_ok
    with _langfuse_init_lock:
        _langfuse_init_ok = None


def _ensure_langfuse_client_with_retry(*, attempts: int = 3, delay_s: float = 0.5) -> bool:
    if _ensure_langfuse_client():
        return True
    for _ in range(max(0, attempts - 1)):
        reset_langfuse_client_cache()
        time.sleep(delay_s)
        if _ensure_langfuse_client():
            return True
    return False


class LangfuseTraceBackend:
    """Trace backend — single owner of Langfuse SDK lifecycle."""

    def get_callback_handler(self) -> Any | None:
        if not _ensure_langfuse_client_with_retry():
            return None
        try:
            from langfuse.langchain import CallbackHandler

            return CallbackHandler()
        except Exception:
            logger.warning("Failed to create Langfuse CallbackHandler", exc_info=True)
            return None

    def start_span(self, ctx) -> str:
        if not _ensure_langfuse_client():
            return ctx.trace_id or ctx.span_name
        try:
            from langfuse import get_client

            client = get_client()
            attrs = dict(ctx.attributes)
            metadata = {k: str(v) for k, v in attrs.items() if v is not None and v != ""}
            engagement_id = (
                attrs.get("engagement_id")
                or attrs.get("investigation_id")
                or attrs.get("correlation_id")
            )
            if engagement_id:
                metadata["langfuse_session_id"] = str(engagement_id)
            tenant_id = attrs.get("tenant_id")
            if tenant_id:
                metadata["langfuse_user_id"] = str(tenant_id)
            tags = []
            if attrs.get("persona"):
                tags.append(f"persona:{attrs['persona']}")
            if attrs.get("job_id"):
                tags.append(f"job:{attrs['job_id']}")
            if engagement_id:
                tags.append(f"engagement:{engagement_id}")
            if tags:
                metadata["langfuse_tags"] = tags
            trace_context = {"trace_id": ctx.trace_id} if ctx.trace_id else None
            observation = client.start_observation(
                name=ctx.span_name,
                as_type="span",
                metadata=metadata or None,
                trace_context=trace_context,
            )
            span_id = str(getattr(observation, "id", ctx.span_name))
            with _spans_lock:
                _active_spans[span_id] = observation
            return span_id
        except Exception:
            logger.warning("Failed to start Langfuse span", exc_info=True)
            return ctx.trace_id or ctx.span_name

    def end_span(self, span_id: str) -> None:
        with _spans_lock:
            observation = _active_spans.pop(span_id, None)
        if observation is None:
            return
        try:
            observation.end()
        except Exception:
            logger.warning("Failed to end Langfuse span", exc_info=True)

    def flush(self) -> None:
        if not settings.langfuse_enabled:
            return
        try:
            from langfuse import get_client

            get_client().flush()
        except Exception:
            logger.warning("Failed to flush Langfuse client", exc_info=True)

    def shutdown(self) -> None:
        if not settings.langfuse_enabled:
            return
        try:
            from langfuse import get_client

            client = get_client()
            client.flush()
            client.shutdown()
        except Exception:
            logger.warning("Failed to shutdown Langfuse client", exc_info=True)


class CompositeTraceBackend:
    """Fan-out trace events to multiple backends."""

    def __init__(self, *backends) -> None:
        self._backends = backends

    def get_callback_handler(self) -> Any | None:
        handlers = [backend.get_callback_handler() for backend in self._backends]
        handlers = [h for h in handlers if h is not None]
        if not handlers:
            return None
        if len(handlers) == 1:
            return handlers[0]
        try:
            from langchain_core.callbacks import CallbackManager

            return CallbackManager(handlers)
        except Exception:
            return handlers[0]

    def start_span(self, ctx) -> str:
        ids = [backend.start_span(ctx) for backend in self._backends]
        return ids[0] if ids else ""

    def end_span(self, span_id: str) -> None:
        for backend in self._backends:
            backend.end_span(span_id)

    def flush(self) -> None:
        for backend in self._backends:
            backend.flush()

    def shutdown(self) -> None:
        for backend in self._backends:
            backend.shutdown()
