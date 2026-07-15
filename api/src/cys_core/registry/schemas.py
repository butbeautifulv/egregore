from __future__ import annotations

from pydantic import BaseModel

from cys_core.domain.findings.models import (
    CloudFinding,
    ComplianceFinding,
    ConductorStepResult,
    ConsultantFinding,
    CriticResult,
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

_SCHEMAS: dict[str, type[BaseModel]] = {
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
    "ConductorStepResult": ConductorStepResult,
    "CriticResult": CriticResult,
    "SchemaGuidedReasoningStep": SchemaGuidedReasoningStep,
    "EngagementPlannerOutput": EngagementPlannerOutput,
    "GeneratePlanPayload": GeneratePlanPayload,
    "AdaptPlanPayload": AdaptPlanPayload,
    "InvestigationPlanStep": InvestigationPlanStep,
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
