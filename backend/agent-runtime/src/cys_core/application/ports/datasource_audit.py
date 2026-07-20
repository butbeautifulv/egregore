from __future__ import annotations

from typing import Any, Protocol


class DatasourceAuditPort(Protocol):
    def append(self, event: dict[str, Any]) -> None: ...
