from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from cys_core.domain.assessment.state import AssessmentState as DomainAssessmentState


class AssessmentState(DomainAssessmentState, TypedDict):
    """LangGraph adapter over the domain assessment state."""

    findings: Annotated[list[dict[str, Any]], operator.add]
    errors: Annotated[list[str], operator.add]
