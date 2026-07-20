from __future__ import annotations

import asyncio
from typing import Any, Protocol

from cys_core.application.policy_resolver import get_profile_policy_resolver
from cys_core.application.ports.catalog import AgentCatalogPort
from cys_core.application.runs.run_budget import nested_delegate_budget
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID, resolve_profile_id


class DelegateRuntime(Protocol):
    async def arun(
        self,
        name: str,
        user_input: str,
        *,
        session_id: str | None = None,
        tenant_id: str = "default",
        investigation_id: str = "",
        profile_id: str = DEFAULT_PROFILE_ID,
    ) -> dict[str, Any]: ...


class DelegateResearch:
    """Delegate a read-only research subtask to a worker persona in-process."""

    def __init__(
        self,
        *,
        runtime: DelegateRuntime,
        catalog: AgentCatalogPort,
        monitor_factory=None,
    ) -> None:
        self._runtime = runtime
        self._catalog = catalog
        self._monitor_factory = monitor_factory

    def _resolve_delegate_persona(self, conductor) -> str:
        delegate_persona = "research"
        if conductor and conductor.capabilities:
            spawn_caps = [cap for cap in conductor.capabilities if cap not in ("spawn_worker", "conductor")]
            if spawn_caps:
                delegate_persona = spawn_caps[0]
        return delegate_persona

    def _monitor(self, profile_id: str):
        if self._monitor_factory is not None:
            return self._monitor_factory("conductor", profile_id=profile_id)
        from cys_core.security.monitor import AgentMonitor

        return AgentMonitor("conductor", profile_id=profile_id)

    async def execute(
        self,
        subtask: str,
        *,
        context_id: str = "",
        tenant_id: str = "default",
    ) -> dict[str, Any]:
        conductor = self._catalog.get_agent("conductor")
        profile_id = resolve_profile_id(catalog_entry=conductor)
        delegate_persona = self._resolve_delegate_persona(conductor)
        monitor = self._monitor(profile_id)
        monitor.log_orchestration_tool(
            context_id or tenant_id,
            "delegate_research",
            {"subtask": subtask[:200], "context_id": context_id},
        )

        inv_id = context_id or f"delegate-{tenant_id}"
        parent_session = f"delegate:research:{inv_id}"
        child_session = f"{parent_session}:child"
        fraction = get_profile_policy_resolver().delegate_budget_fraction(profile_id)
        with nested_delegate_budget(parent_session, child_session, fraction=fraction):
            result = await self._runtime.arun(
                delegate_persona,
                subtask,
                session_id=child_session,
                tenant_id=tenant_id,
                investigation_id=inv_id,
                profile_id=profile_id,
            )
        payload = result if isinstance(result, dict) else {"raw": result}
        monitor.log_orchestration_tool(
            context_id or tenant_id,
            "delegate_research",
            {"subtask": subtask[:200]},
            outcome="ok" if "error" not in payload else "error",
        )
        return payload

    def execute_sync(
        self,
        subtask: str,
        *,
        context_id: str = "",
        tenant_id: str = "default",
    ) -> dict[str, Any]:
        return asyncio.run(self.execute(subtask, context_id=context_id, tenant_id=tenant_id))
