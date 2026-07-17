from __future__ import annotations

import asyncio
import json
import threading
from dataclasses import dataclass
from typing import Any

import httpx

from interfaces.gateways.tool.server import handle_connection


@dataclass
class _GatewayResponse:
    status_code: int
    _body: bytes

    def json(self) -> Any:
        return json.loads(self._body)

    @property
    def text(self) -> str:
        return self._body.decode("utf-8")


class GatewayTestClient:
    """fastapi.testclient.TestClient-shaped wrapper around the real asyncio
    Tool Gateway server (interfaces.gateways.tool.server), listening on an
    ephemeral localhost port in a background thread. Only implements the
    .get()/.post() surface the gateway test suite actually uses, so real
    wire-protocol behavior (parsing, auth, status codes) is exercised end to
    end instead of mocked."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self._server: asyncio.base_events.Server | None = None
        self._port = 0
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=5):
            raise RuntimeError("tool gateway test server failed to start")
        # trust_env=False: this client only ever talks to a localhost port
        # this same process just bound — an ambient HTTP_PROXY/ALL_PROXY in
        # the shell environment must never be consulted for it (and some
        # proxy configs, e.g. bare "socks://" instead of "socks5://", make
        # httpx raise at Client construction time rather than just being
        # irrelevant).
        self._client = httpx.Client(base_url=f"http://127.0.0.1:{self._port}", timeout=10.0, trust_env=False)

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._serve())

    async def _serve(self) -> None:
        self._server = await asyncio.start_server(handle_connection, "127.0.0.1", 0)
        self._port = self._server.sockets[0].getsockname()[1]
        self._ready.set()
        async with self._server:
            await self._server.serve_forever()

    def get(self, path: str, *, headers: dict[str, str] | None = None) -> _GatewayResponse:
        resp = self._client.get(path, headers=headers)
        return _GatewayResponse(resp.status_code, resp.content)

    def post(
        self,
        path: str,
        *,
        json: Any = None,
        headers: dict[str, str] | None = None,
    ) -> _GatewayResponse:
        resp = self._client.post(path, json=json, headers=headers)
        return _GatewayResponse(resp.status_code, resp.content)

    def close(self) -> None:
        self._client.close()
        if self._server is not None:
            self._loop.call_soon_threadsafe(self._server.close)
        self._thread.join(timeout=5)

    def __enter__(self) -> GatewayTestClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
