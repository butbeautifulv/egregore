from __future__ import annotations

from pydantic import BaseModel

from cys_core.schemas.findings import (
    ComplianceFinding,
    CriticResult,
    NetworkFinding,
    RedTeamFinding,
    SocFinding,
)

_SCHEMAS: dict[str, type[BaseModel]] = {
    "RedTeamFinding": RedTeamFinding,
    "NetworkFinding": NetworkFinding,
    "SocFinding": SocFinding,
    "ComplianceFinding": ComplianceFinding,
    "CriticResult": CriticResult,
}


class SchemaRegistry:
    def get(self, name: str | None) -> type[BaseModel] | None:
        if not name:
            return None
        if name not in _SCHEMAS:
            raise KeyError(f"Unknown schema: {name}")
        return _SCHEMAS[name]

    def names(self) -> list[str]:
        return list(_SCHEMAS.keys())


schema_registry = SchemaRegistry()
