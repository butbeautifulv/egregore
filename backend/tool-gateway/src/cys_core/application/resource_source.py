from __future__ import annotations

from cys_core.application.ports.resource_source import ResourceSourcePort

_source: ResourceSourcePort | None = None


def configure_resource_source(port: ResourceSourcePort) -> None:
    global _source
    _source = port


def get_resource_source() -> ResourceSourcePort:
    if _source is None:
        raise RuntimeError("Resource source not configured — wire via bootstrap Container")
    return _source
