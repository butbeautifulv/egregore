from __future__ import annotations

import os

from pydantic import BaseModel

from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.domain.findings.models import ConductorStepResult, CriticResult
from cys_core.domain.findings.packs.cybersec_soc import (
    CloudFinding,
    ComplianceFinding,
    ConsultantFinding,
    DfirFinding,
    HunterFinding,
    IdentityFinding,
    IntelFinding,
    NetworkFinding,
    PurpleFinding,
    RedTeamFinding,
    SocFinding,
)
from cys_core.domain.reasoning.sgr_models import SchemaGuidedReasoningStep
from cys_core.domain.runs.plan_models import (
    AdaptPlanPayload,
    EngagementPlannerOutput,
    GeneratePlanPayload,
    InvestigationPlanStep,
)

# Generic schemas (control-plane / planning) — resolvable regardless of the
# active profile pack. Pack-specific Finding schemas live in _PACK_SCHEMAS,
# keyed by profile-pack id, and are only registered for their own pack — see
# cys_core/registry/tools.py's _active_tool_domains() for the same
# PROFILE_PACK_ID-gated pattern applied to tool registration (§8.4 point 4).
_GENERIC_SCHEMAS: dict[str, type[BaseModel]] = {
    "ConductorStepResult": ConductorStepResult,
    "CriticResult": CriticResult,
    "SchemaGuidedReasoningStep": SchemaGuidedReasoningStep,
    "EngagementPlannerOutput": EngagementPlannerOutput,
    "GeneratePlanPayload": GeneratePlanPayload,
    "AdaptPlanPayload": AdaptPlanPayload,
    "InvestigationPlanStep": InvestigationPlanStep,
}

_PACK_SCHEMAS: dict[str, dict[str, type[BaseModel]]] = {
    DEFAULT_PROFILE_ID: {
        "RedTeamFinding": RedTeamFinding,
        "NetworkFinding": NetworkFinding,
        "SocFinding": SocFinding,
        "ComplianceFinding": ComplianceFinding,
        "ConsultantFinding": ConsultantFinding,
        "IntelFinding": IntelFinding,
        "HunterFinding": HunterFinding,
        "IdentityFinding": IdentityFinding,
        "DfirFinding": DfirFinding,
        "CloudFinding": CloudFinding,
        "PurpleFinding": PurpleFinding,
    },
}


def _active_pack_schemas() -> dict[str, type[BaseModel]]:
    pack_id = os.environ.get("PROFILE_PACK_ID", DEFAULT_PROFILE_ID)
    return _PACK_SCHEMAS.get(pack_id, {})


class SchemaRegistry:
    def get(self, name: str | None) -> type[BaseModel] | None:
        if not name:
            return None
        schemas = {**_GENERIC_SCHEMAS, **_active_pack_schemas()}
        if name not in schemas:
            raise KeyError(f"Unknown schema: {name}")
        return schemas[name]

    def names(self) -> list[str]:
        return list({**_GENERIC_SCHEMAS, **_active_pack_schemas()}.keys())


schema_registry = SchemaRegistry()
