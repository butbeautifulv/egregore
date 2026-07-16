from __future__ import annotations

from typing import Any

from cys_core.application.ports.datasource_audit import DatasourceAuditPort
from cys_core.infrastructure.datasources.audit_sink import append_datasource_audit_event


class DatasourceAuditAdapter:
    def append(self, event: dict[str, Any]) -> None:
        append_datasource_audit_event(event)


def build_datasource_audit_port() -> DatasourceAuditPort:
    return DatasourceAuditAdapter()
