from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DataSourceStaging = Literal["draft", "vetted", "builtin"]


class WriteGateRequest(BaseModel):
    actor: str
    reason: str
    diff_summary: str = ""


class PromotionRule(BaseModel):
    from_status: DataSourceStaging
    to_status: DataSourceStaging
    required_role: str = "operator"


class DataSourceGovernance(BaseModel):
    staging_default: DataSourceStaging = "draft"
    write_gate_required: bool = True
    promotion_rules: list[PromotionRule] = Field(
        default_factory=lambda: [
            PromotionRule(from_status="draft", to_status="vetted", required_role="operator"),
            PromotionRule(from_status="vetted", to_status="builtin", required_role="admin"),
        ]
    )
