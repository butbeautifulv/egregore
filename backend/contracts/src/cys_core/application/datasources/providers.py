from __future__ import annotations

from cys_core.application.ports.datasource_audit import DatasourceAuditPort
from cys_core.application.ports.datasource_catalog import DataSourceCatalogPort

_catalog: DataSourceCatalogPort | None = None
_audit: DatasourceAuditPort | None = None


def configure_datasource_catalog(port: DataSourceCatalogPort) -> None:
    global _catalog
    _catalog = port


def get_datasource_catalog_port() -> DataSourceCatalogPort:
    if _catalog is None:
        raise RuntimeError("DataSource catalog not configured — wire via bootstrap Container")
    return _catalog


def configure_datasource_audit(port: DatasourceAuditPort) -> None:
    global _audit
    _audit = port


def get_datasource_audit_port() -> DatasourceAuditPort:
    if _audit is None:
        raise RuntimeError("Datasource audit not configured — wire via bootstrap Container")
    return _audit
