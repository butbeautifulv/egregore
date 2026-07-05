from __future__ import annotations

from typing import Protocol

from cys_core.domain.tools.models import ToolInvokeCommand, ToolInvokeResult


class ToolExecutionGatewayPort(Protocol):
    """Execution boundary for sandbox tool invokes (PEP)."""

    def invoke(self, command: ToolInvokeCommand) -> ToolInvokeResult: ...
