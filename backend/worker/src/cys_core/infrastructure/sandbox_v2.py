from __future__ import annotations

import uuid

from cys_core.domain.workers.models import SandboxCredentials, WorkloadHandle, WorkloadSpec


class WorkloadHandleImpl(WorkloadHandle):
    pass


class DockerSandboxConnector:
    """Docker sandbox v2 stub — returns metadata-compatible handle."""

    name = "docker"

    def create_workload(self, spec: WorkloadSpec) -> WorkloadHandleImpl:
        wid = f"docker-{spec.engagement_id}-{uuid.uuid4().hex[:8]}"
        return WorkloadHandleImpl(
            workload_id=wid,
            sandbox_id=wid,
            endpoint=f"sandbox://docker/{spec.persona}/{spec.engagement_id}",
        )

    def destroy_workload(self, handle: WorkloadHandle) -> None:
        return None

    def create(self, run_id: str, persona: str, policy: str = "default") -> SandboxCredentials:
        handle = self.create_workload(
            WorkloadSpec(persona=persona, engagement_id=run_id, image="egregore-agent:latest", policy=policy)
        )
        return SandboxCredentials(
            sandbox_id=handle.sandbox_id,
            endpoint=handle.endpoint,
            token=f"tok-{policy}-{run_id}",
        )

    def destroy(self, run_id: str) -> None:
        return None

    async def acreate(self, run_id: str, persona: str, policy: str = "default") -> SandboxCredentials:
        return self.create(run_id, persona, policy)

    async def adestroy(self, run_id: str) -> None:
        self.destroy(run_id)
