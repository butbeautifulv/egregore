from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from pydantic import ValidationError

from interfaces.gateways.model.auth import GatewayAuthError, require_gateway_secret
from interfaces.gateways.model.handler import invoke_model
from interfaces.gateways.model.models import ModelInvokeRequest

logger = logging.getLogger(__name__)

_REASON_PHRASES = {
    200: "OK",
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    422: "Unprocessable Entity",
    500: "Internal Server Error",
}


class _HttpError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


class _ConnectionClosed(Exception):
    """Client disconnected mid-request — nothing to respond with."""


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload).encode("utf-8")


async def _read_headers(reader: asyncio.StreamReader) -> tuple[str, str, dict[str, str]]:
    request_line = await reader.readline()
    if not request_line:
        raise _ConnectionClosed
    try:
        method, path, _version = request_line.decode("latin-1").strip().split(" ", 2)
    except ValueError as exc:
        raise _HttpError(400, "malformed request line") from exc
    headers: dict[str, str] = {}
    while True:
        line = await reader.readline()
        if not line or line in (b"\r\n", b"\n"):
            break
        key, sep, value = line.decode("latin-1").partition(":")
        if sep:
            headers[key.strip().lower()] = value.strip()
    return method, path, headers


async def _read_body(reader: asyncio.StreamReader, headers: dict[str, str]) -> bytes:
    length = int(headers.get("content-length", "0") or "0")
    if length <= 0:
        return b""
    return await reader.readexactly(length)


async def _route(method: str, path: str, headers: dict[str, str], body: bytes) -> tuple[int, bytes, str]:
    if method == "GET" and path == "/health":
        return 200, _json_bytes({"status": "ok"}), "application/json"

    if method == "POST" and path == "/v1/model/invoke":
        try:
            require_gateway_secret(headers.get("authorization"))
        except GatewayAuthError as exc:
            raise _HttpError(exc.status_code, exc.detail) from exc
        try:
            data = json.loads(body or b"{}")
        except json.JSONDecodeError as exc:
            raise _HttpError(400, f"invalid JSON body: {exc}") from exc
        try:
            request = ModelInvokeRequest.model_validate(data)
        except ValidationError as exc:
            raise _HttpError(422, str(exc)) from exc
        # No asyncio.to_thread wrap needed here (unlike tool-gateway's server.py) —
        # invoke_model's whole chain (sanitize -> litellm.acompletion) is genuinely
        # async end to end, not a sync call chain being offloaded to a thread.
        response = await invoke_model(request)
        return 200, response.model_dump_json().encode("utf-8"), "application/json"

    raise _HttpError(404, "not found")


async def _build_response(reader: asyncio.StreamReader) -> tuple[int, bytes, str]:
    method, path, headers = await _read_headers(reader)
    body = await _read_body(reader, headers)
    try:
        return await _route(method, path, headers, body)
    except _HttpError as exc:
        return exc.status_code, _json_bytes({"detail": exc.detail}), "application/json"
    except Exception:
        logger.exception("model gateway request failed", extra={"path": path})
        return 500, _json_bytes({"detail": "internal server error"}), "application/json"


async def handle_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        status, resp_body, content_type = await _build_response(reader)
    except _HttpError as exc:
        status, resp_body, content_type = exc.status_code, _json_bytes({"detail": exc.detail}), "application/json"
    except _ConnectionClosed:
        writer.close()
        return
    except (asyncio.IncompleteReadError, ConnectionError):
        writer.close()
        return
    reason = _REASON_PHRASES.get(status, "OK")
    header_bytes = (
        f"HTTP/1.1 {status} {reason}\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(resp_body)}\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).encode("latin-1")
    writer.write(header_bytes + resp_body)
    try:
        await writer.drain()
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except (ConnectionError, OSError):
            pass


async def start_server(host: str = "0.0.0.0", port: int = 8093) -> asyncio.base_events.Server:
    """Bind and start listening; caller owns the returned server's lifecycle
    (used directly by tests on an ephemeral port, and by serve_forever below
    for real deployments)."""
    return await asyncio.start_server(handle_connection, host, port)


async def serve_forever(host: str = "0.0.0.0", port: int = 8093) -> None:
    server = await start_server(host, port)
    async with server:
        await server.serve_forever()


__all__ = ["handle_connection", "serve_forever", "start_server"]
