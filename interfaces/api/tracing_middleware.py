from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import Response

from cys_core.observability.tracing import bind_from_carrier, reset_correlation_id
from cys_core.observability.worker_spans import observability_span


async def tracing_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    headers = {k: v for k, v in request.headers.items()}
    cid_token = bind_from_carrier(headers)
    try:
        with observability_span(
            "api.request",
            method=request.method,
            path=request.url.path,
        ):
            return await call_next(request)
    finally:
        if cid_token is not None:
            reset_correlation_id(cid_token)
