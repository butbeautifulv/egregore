"""OpenFGA SDK adapter — optional dependency; falls back to raise if missing in enforce."""

from __future__ import annotations

import structlog

from cys_core.application.ports.authz import AuthzCheck, AuthzTuple

logger = structlog.get_logger(__name__)


class OpenFgaAuthzPort:
    def __init__(
        self,
        *,
        api_url: str,
        store_id: str,
        api_token: str = "",
        model_id: str = "",
    ) -> None:
        self._api_url = api_url.rstrip("/")
        self._store_id = store_id
        self._api_token = api_token
        self._model_id = model_id

    def _build_client(self):
        try:
            from openfga_sdk import ClientConfiguration, OpenFgaClient
        except ImportError as exc:
            raise RuntimeError("openfga-sdk not installed") from exc
        credentials = None
        if self._api_token:
            try:
                from openfga_sdk.credentials import CredentialConfiguration, Credentials

                credentials = Credentials(
                    method="api_token",
                    configuration=CredentialConfiguration(api_token=self._api_token),
                )
            except Exception:
                logger.warning("openfga_token_credentials_unavailable")
        config = ClientConfiguration(
            api_url=self._api_url,
            store_id=self._store_id,
            credentials=credentials,
            authorization_model_id=self._model_id or None,
        )
        return OpenFgaClient(config)

    def _run(self, coroutine_factory):
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(lambda: asyncio.run(coroutine_factory())).result()
        return asyncio.run(coroutine_factory())

    def check(self, req: AuthzCheck) -> bool:
        from openfga_sdk.client.models import ClientCheckRequest

        body = ClientCheckRequest(
            user=req.user,
            relation=req.relation,
            object=req.object,
        )

        async def _run():
            client = self._build_client()
            try:
                return await client.check(body)
            finally:
                await client.close()

        result = self._run(_run)
        return bool(getattr(result, "allowed", False))

    def list_objects(self, *, user: str, relation: str, object_type: str) -> list[str]:
        from openfga_sdk.client.models import ClientListObjectsRequest

        body = ClientListObjectsRequest(
            user=user,
            relation=relation,
            type=object_type,
        )

        async def _run():
            client = self._build_client()
            try:
                return await client.list_objects(body)
            finally:
                await client.close()

        result = self._run(_run)
        objects = getattr(result, "objects", None) or []
        return list(objects)

    def write_tuples(self, tuples: list[AuthzTuple]) -> None:
        if not tuples:
            return
        from openfga_sdk.client.models import ClientTuple, ClientWriteRequest

        writes = [ClientTuple(user=t.user, relation=t.relation, object=t.object) for t in tuples]
        body = ClientWriteRequest(writes=writes)

        async def _run():
            client = self._build_client()
            try:
                return await client.write(body)
            finally:
                await client.close()

        self._run(_run)

    def delete_tuples(self, tuples: list[AuthzTuple]) -> None:
        if not tuples:
            return
        from openfga_sdk.client.models import ClientTuple, ClientWriteRequest

        deletes = [ClientTuple(user=t.user, relation=t.relation, object=t.object) for t in tuples]
        body = ClientWriteRequest(deletes=deletes)

        async def _run():
            client = self._build_client()
            try:
                return await client.write(body)
            finally:
                await client.close()

        self._run(_run)

    def ping(self) -> bool:
        try:
            async def _run():
                client = self._build_client()
                await client.close()
                return True

            return bool(self._run(_run))
        except Exception as exc:
            logger.warning("openfga_ping_failed", error=str(exc))
            return False
