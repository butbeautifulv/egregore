from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.domain.reasoning.sgr_models import SgrPolicy


class CatalogSource(str, Enum):
    FILESYSTEM = "filesystem"
    API = "api"
    SEED = "seed"


class StagingStatus(str, Enum):
    DRAFT = "draft"
    VETTED = "vetted"
    BUILTIN = "builtin"


class CapabilityBinding(BaseModel):
    capability_id: str
    capability_type: str  # tool | skill
    trust_tier: str = "builtin"


class PersonaQuality(BaseModel):
    # Catalog YAML / profile pack is the runtime source of truth for persona quality defaults.
    empirical_trust: float = 0.75
    critic_pass_rate: float = 0.0
    trace_critic_pass_rate: float = 0.0
    factuality_score: float = 0.0
    faithfulness_score: float = 0.0
    hitl_rate: float = 0.0
    avg_cost_usd: float = 0.0
    job_success_rate: float = 0.0
    sample_size: int = 0
    last_evaluated_at: datetime | None = None


class SkillQuality(BaseModel):
    usage_count: int = 0
    load_errors: int = 0


class PlanQuality(BaseModel):
    match_count: int = 0
    false_positive_rate: float = 0.0
    avg_jobs_per_event: float = 0.0


class TraceCriticPolicy(BaseModel):
    enabled: bool = True
    # TRACE_CRITIC_* env overrides applied via ProfilePolicyResolver.env_overrides_from_settings.
    threshold: float = 0.55
    every_n_steps: int = 3
    rerun_max: int = 2
    hitl_on_exhausted: bool = True
    use_reasoning: bool = False


class AnomalyPolicy(BaseModel):
    tool_calls_per_minute: int = 30
    failed_tool_calls: int = 5
    injection_attempts: int = 1
    sensitive_data_access: int = 3


class QualitySignals(BaseModel):
    # Catalog YAML / profile pack is the runtime source of truth for quality signal weights.
    job_success: float = 0.85
    job_failure: float = 0.35
    trace_critic_pass: float = 0.8
    trace_critic_fail: float = 0.4
    hitl_pause: float = 0.5
    bus_failure: float = 0.25
    ema_alpha: float = 0.15


class ModePolicyPayload(BaseModel):
    read_only_tools: list[str] = Field(default_factory=list)
    plan_blocked_tools: list[str] = Field(default_factory=list)
    mutating_tools: list[str] = Field(default_factory=lambda: ["spawn_worker", "update_todos"])


class ProfilePolicyPayload(BaseModel):
    # Catalog YAML / profile pack is the runtime source of truth for profile policy defaults.
    trust_floor: float = 0.5
    bus_policy: dict[str, list[str]] = Field(default_factory=dict)
    breaker_failure_threshold: int = 5
    breaker_reset_seconds: int = 60
    tool_allowlist: dict[str, list[str] | None] = Field(default_factory=dict)
    tool_risk: dict[str, str] = Field(default_factory=dict)
    datasource_allowlist: dict[str, list[str] | None] = Field(default_factory=dict)
    persona_datasource_allowlist: dict[str, dict[str, list[str]]] = Field(default_factory=dict)
    datasource_capability_grants: dict[str, dict[str, list[str]]] = Field(default_factory=dict)
    hitl_auto_approve_threshold: str = "low"
    mode_policy: ModePolicyPayload = Field(default_factory=ModePolicyPayload)
    escalation_paths: list[list[str]] = Field(default_factory=list)
    max_spawn_depth: int = 5
    cost_per_1k_tokens_usd: float = 0.003
    delegate_budget_fraction: float = 0.35
    trace_critic: TraceCriticPolicy = Field(default_factory=TraceCriticPolicy)
    anomaly: AnomalyPolicy = Field(default_factory=AnomalyPolicy)
    quality_signals: QualitySignals = Field(default_factory=QualitySignals)
    notify_control_severities: list[str] = Field(default_factory=lambda: ["high", "critical"])
    sgr: SgrPolicy = Field(default_factory=SgrPolicy)


class AgentCatalogEntry(BaseModel):
    name: str
    description: str = ""
    role: str = "worker"
    output_schema: str | None = None
    tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    hitl_tools: dict[str, bool] = Field(default_factory=dict)
    trust_level: str = "internal"
    bus_recipients: list[str] = Field(default_factory=list)
    persona_prompt: str = ""
    sample_input: str | None = None
    language: str = "ru"
    system_prompt: str = ""
    system_prompt_digest: str = ""
    profile_id: str = DEFAULT_PROFILE_ID
    version: int = 1
    version_tag: str = ""
    source: CatalogSource = CatalogSource.FILESYSTEM
    enabled: bool = True
    tags: list[str] = Field(default_factory=list)
    quality: PersonaQuality = Field(default_factory=PersonaQuality)
    budget_max_tokens: int | None = None
    budget_max_cost_usd: float | None = None
    budget_max_tool_calls: int | None = None
    data_clearance: str = "internal"
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SkillCatalogEntry(BaseModel):
    id: str
    profile_id: str = DEFAULT_PROFILE_ID
    name: str = ""
    description: str = ""
    body: str = ""
    content_hash: str = ""
    trust_tier: str = "builtin"
    staging_status: StagingStatus = StagingStatus.BUILTIN
    enabled: bool = True
    version: int = 1
    quality: SkillQuality = Field(default_factory=SkillQuality)
    source: CatalogSource = CatalogSource.FILESYSTEM
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PlanCatalogEntry(BaseModel):
    id: str
    profile_id: str = DEFAULT_PROFILE_ID
    name: str = ""
    description: str = ""
    rules: list[dict] = Field(default_factory=list)
    enabled: bool = True
    active: bool = False
    version: int = 1
    quality: PlanQuality = Field(default_factory=PlanQuality)
    source: CatalogSource = CatalogSource.FILESYSTEM
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class McpServerEntry(BaseModel):
    id: str
    url: str
    trust_tier: str = "internal"
    allowed_tools: list[str] = Field(default_factory=list)
    enabled: bool = True
    health_status: str = "unknown"
    profile_id: str = DEFAULT_PROFILE_ID
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PlannerRule(BaseModel):
    name: str
    when: dict[str, Any] = Field(default_factory=dict)
    personas: list[str] = Field(default_factory=list)
    execution_mode: str | None = None
    sub_goals: dict[str, str] = Field(default_factory=dict)
    rationale: str = ""


class PlannerPack(BaseModel):
    persona: str = "planner"
    prompt_template: str = ""
    rules: list[PlannerRule] = Field(default_factory=list)
    synthesis_default: str = "consultant"
    post_processors: list[str] = Field(default_factory=list)


class ProfilePack(BaseModel):
    id: str
    name: str
    description: str = ""
    default_personas: list[str] = Field(default_factory=list)
    default_skills: list[str] = Field(default_factory=list)
    default_plan: str = "incident-triage"
    control_plane_mode: str = "gate_only"
    global_rules: str = ""
    hints_template: str = ""
    policy: ProfilePolicyPayload = Field(default_factory=ProfilePolicyPayload)
    planner: PlannerPack | None = None
    intake_schema: dict[str, Any] = Field(default_factory=dict)


class ToolCatalogEntry(BaseModel):
    id: str
    profile_id: str = DEFAULT_PROFILE_ID
    name: str
    description: str = ""
    risk_tier: str = "medium"
    handler: str = "builtin"
    enabled: bool = True
    source: CatalogSource = CatalogSource.FILESYSTEM
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CatalogVersion(BaseModel):
    profile_id: str
    version: int = 1
    agent_count: int = 0
