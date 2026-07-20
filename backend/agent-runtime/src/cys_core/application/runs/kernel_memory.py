from __future__ import annotations

from cys_core.domain.runs.kernel_models import RunKernelRequest
from cys_core.domain.runs.trace_models import MemoryTraceFields, memory_trace
from cys_core.domain.runs.trajectory import AgentTrajectory


def record_memory_read(
    trajectory: AgentTrajectory,
    request: RunKernelRequest,
    *,
    entries: int,
) -> None:
    if entries <= 0:
        return
    trajectory.record(
        memory_trace(
            "memory_read",
            MemoryTraceFields(
                operation="memory_read",
                tenant_id=request.tenant_id,
                investigation_id=request.investigation_id,
                entries=entries,
            ),
        )
    )


def record_memory_write(
    trajectory: AgentTrajectory,
    request: RunKernelRequest,
    *,
    memory_type: str,
    size: int = 0,
) -> None:
    trajectory.record(
        memory_trace(
            "memory_write",
            MemoryTraceFields(
                operation="memory_write",
                tenant_id=request.tenant_id,
                investigation_id=request.investigation_id,
                memory_type=memory_type,
                size=size,
            ),
        )
    )
