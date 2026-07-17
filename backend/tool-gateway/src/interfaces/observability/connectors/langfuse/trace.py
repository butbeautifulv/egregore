from __future__ import annotations

import logging
import threading
from typing import Any, cast

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


class LangfuseTraceBackend:
    """Trace backend — single owner of Langfuse SDK lifecycle."""

    def get_callback_handler(self) -> Any | None:
        # NOTE: this is on the hot path — called once per LLM invocation via
        # model_connector.callbacks(). Must stay non-blocking: _ensure_langfuse_client()
        # is cached and returns immediately. A previous version called a retry wrapper
        # that reset the cache and did a blocking time.sleep() (up to 1.5s) on every
        # single call for as long as Langfuse stayed unreachable — that stalled the
        # asyncio event loop on every LLM turn during any Langfuse hiccup. Use
        # reset_langfuse_client_cache() from a periodic health check if a retry is
        # ever needed, not from this call path.
        if not _ensure_langfuse_client():
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
            metadata: dict[str, Any] = {k: str(v) for k, v in attrs.items() if v is not None and v != ""}
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
                metadata=cast(Any, metadata or None),
                trace_context=cast(Any, trace_context),
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
        # Only ever returns a single handler: OtelTraceBackend.get_callback_handler()
        # always returns None, so LangfuseTraceBackend is the only sink that can
        # produce one here. No langchain_core.callbacks.CallbackManager merge
        # needed — see docs/MICROSERVICES_SPLIT_PLAN.md §21.1 (same finding/fix
        # already applied to api's copy of this file).
        handlers = [backend.get_callback_handler() for backend in self._backends]
        handlers = [h for h in handlers if h is not None]
        return handlers[0] if handlers else None

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
