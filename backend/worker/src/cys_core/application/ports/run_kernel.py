from __future__ import annotations

from typing import Protocol

from cys_core.domain.runs.kernel_models import RunKernelRequest, RunKernelResult


class RunKernelPort(Protocol):
    """Unified execution port for interactive and worker runs."""

    async def execute(self, request: RunKernelRequest) -> RunKernelResult: ...
