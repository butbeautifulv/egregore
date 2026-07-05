from __future__ import annotations

import uuid

from bootstrap.settings import Settings, get_settings
from cys_core.domain.workers.models import SandboxCredentials


class LocalSandboxConnector:
    """In-process sandbox stub for dev/test — simulates ephemeral worker isolation."""

    name = "local"

    def __init__(self) -> None:
        self._active: dict[str, SandboxCredentials] = {}

    def create(self, run_id: str, persona: str, policy: str = "default") -> SandboxCredentials:
        creds = SandboxCredentials(
            sandbox_id=f"local-{run_id}-{uuid.uuid4().hex[:8]}",
            endpoint=f"sandbox://local/{persona}/{run_id}",
            token=f"tok-{policy}-{run_id}",
        )
        self._active[run_id] = creds
        return creds

    def destroy(self, run_id: str) -> None:
        self._active.pop(run_id, None)

    async def acreate(self, run_id: str, persona: str, policy: str = "default") -> SandboxCredentials:
        return self.create(run_id, persona, policy)

    async def adestroy(self, run_id: str) -> None:
        self.destroy(run_id)

    def is_active(self, run_id: str) -> bool:
        return run_id in self._active


_sandbox_connector: LocalSandboxConnector | None = None


def get_sandbox_connector(
    *,
    settings: Settings | None = None,
) -> LocalSandboxConnector:
    """Return sandbox connector; K8s when SANDBOX_CONNECTOR=k8s."""
    global _sandbox_connector
    cfg = settings or get_settings()
    if _sandbox_connector is not None and settings is None:
        return _sandbox_connector
    if cfg.sandbox_connector == "k8s":
        from cys_core.infrastructure.k8s_sandbox import K8sSandboxConnector

        connector: LocalSandboxConnector = K8sSandboxConnector(settings=cfg)
    elif cfg.egregore_sandbox_v2:
        from cys_core.infrastructure.sandbox_v2 import DockerSandboxConnector

        connector = DockerSandboxConnector()
    else:
        connector = LocalSandboxConnector()
    if settings is None:
        _sandbox_connector = connector
    return connector


def reset_sandbox_connector_cache() -> None:
    global _sandbox_connector
    _sandbox_connector = None
