from __future__ import annotations

from typing import Protocol

from cys_core.domain.tools.models import ToolInvokeCommand, ToolInvokeResult


class ToolInvokePort(Protocol):
    def execute(self, command: ToolInvokeCommand) -> ToolInvokeResult: ...
