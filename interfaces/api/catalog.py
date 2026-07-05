from __future__ import annotations

from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from bootstrap.container import get_container
from cys_core.application.use_cases.upsert_catalog_agent import UpsertCatalogAgent
from cys_core.application.use_cases.upsert_catalog_resource import (
    UpsertMcpServer,
    UpsertPlan,
    UpsertSkill,
    UpsertTool,
)
from cys_core.application.use_cases.upsert_profile_pack import UpsertProfilePack
from cys_core.application.use_cases.upsert_profile_policy import UpsertProfilePolicy
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.domain.security.auth_models import AuthClaims
from interfaces.api.auth import require_operator_role, require_reader_role
from interfaces.api.deps import api_actor

router = APIRouter(prefix="/catalog", tags=["catalog"])


class AgentCatalogOut(BaseModel):
    name: str
    description: str = ""
    role: str = ""
    output_schema: str | None = None
    tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    profile_id: str = ""
    version: int = 1
    version_tag: str = ""
    enabled: bool = True
    empirical_trust: float = 0.75


class AgentCatalogDetailOut(AgentCatalogOut):
    system_prompt: str = ""
    system_prompt_digest: str = ""


class AgentCatalogPut(BaseModel):
    description: str = ""
    role: str = "worker"
    output_schema: str | None = None
    tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    trust_level: str = "internal"
    bus_recipients: list[str] = Field(default_factory=list)
    enabled: bool = True
    profile_id: str = DEFAULT_PROFILE_ID
    system_prompt: str = ""
    version_tag: str = ""
    budget_max_tokens: int | None = None
    budget_max_cost_usd: float | None = None
    budget_max_tool_calls: int | None = None
    data_clearance: str = "internal"


class ToolCatalogPut(BaseModel):
    name: str = ""
    description: str = ""
    risk_tier: str = "medium"
    handler: str = "builtin"
    enabled: bool = True
    profile_id: str = DEFAULT_PROFILE_ID


class ProfilePolicyPut(BaseModel):
    policy: dict = Field(default_factory=dict)


class SkillCatalogPut(BaseModel):
    name: str = ""
    description: str = ""
    body: str = ""
    profile_id: str = DEFAULT_PROFILE_ID
    trust_tier: str = "community"
    staging_status: str = "draft"


class PlanCatalogPut(BaseModel):
    name: str = ""
    description: str = ""
    rules: list[dict] = Field(default_factory=list)
    profile_id: str = DEFAULT_PROFILE_ID
    enabled: bool = True


class McpServerPut(BaseModel):
    url: str
    trust_tier: str = "internal"
    allowed_tools: list[str] = Field(default_factory=list)
    enabled: bool = True
    profile_id: str = DEFAULT_PROFILE_ID


class ProfilePackPut(BaseModel):
    name: str
    description: str = ""
    default_personas: list[str] = Field(default_factory=list)
    default_skills: list[str] = Field(default_factory=list)
    policy: dict = Field(default_factory=dict)


def _container():
    return get_container()


def _mutation():
    return get_container().get_catalog_mutation_service()


def _entry_out(entry) -> AgentCatalogOut:
    return AgentCatalogOut(
        name=entry.name,
        description=entry.description,
        role=entry.role,
        output_schema=entry.output_schema,
        tools=entry.tools,
        skills=entry.skills,
        profile_id=entry.profile_id,
        version=entry.version,
        version_tag=entry.version_tag,
        enabled=entry.enabled,
        empirical_trust=entry.quality.empirical_trust,
    )


def _detail_out(entry) -> AgentCatalogDetailOut:
    return AgentCatalogDetailOut(
        name=entry.name,
        description=entry.description,
        role=entry.role,
        output_schema=entry.output_schema,
        tools=entry.tools,
        skills=entry.skills,
        profile_id=entry.profile_id,
        version=entry.version,
        version_tag=entry.version_tag,
        enabled=entry.enabled,
        empirical_trust=entry.quality.empirical_trust,
        system_prompt=entry.system_prompt,
        system_prompt_digest=entry.system_prompt_digest,
    )


@router.get("/agents")
async def list_agents(
    profile_id: str | None = None,
    enabled: bool | None = None,
    _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
) -> dict[str, Any]:
    enabled_only = False
    agents = _container().get_agent_catalog().list_agents(profile_id=profile_id, enabled_only=enabled_only)
    if enabled is not None:
        agents = [agent for agent in agents if agent.enabled == enabled]
    return {"agents": [_entry_out(a).model_dump() for a in agents]}


@router.get("/agents/{name}")
async def get_agent(
    name: str,
    _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
) -> AgentCatalogDetailOut:
    entry = _container().get_agent_catalog().get_agent(name)
    if entry is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return _detail_out(entry)


@router.put("/agents/{name}")
async def put_agent(
    name: str,
    body: AgentCatalogPut,
    _auth: Annotated[AuthClaims | None, Depends(require_operator_role)] = None,
) -> AgentCatalogOut:
    saved = UpsertCatalogAgent(
        _container().get_agent_catalog(),
        schema_registry=get_container().get_schema_registry_port(),
        reload=_container().reload_catalog,
        mutation=_mutation(),
    ).execute(
        name,
        body.model_dump(),
        actor=api_actor(_auth),
    )
    return _entry_out(saved)


@router.delete("/agents/{name}")
async def delete_agent(
    name: str,
    profile_id: str = DEFAULT_PROFILE_ID,
    _auth: Annotated[AuthClaims | None, Depends(require_operator_role)] = None,
) -> dict[str, Any]:
    ok = _mutation().delete_agent(
        name,
        profile_id=profile_id,
        actor=api_actor(_auth),
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"deleted": True, "name": name}


@router.get("/skills")
async def list_skills(
    profile_id: str | None = None,
    _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
) -> dict[str, Any]:
    skills = _container().get_skill_catalog().list_skills(profile_id=profile_id, enabled_only=False)
    return {"skills": [skill.model_dump(mode="json") for skill in skills]}


@router.get("/skills/{skill_id}")
async def get_skill(
    skill_id: str,
    profile_id: str = DEFAULT_PROFILE_ID,
    _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
) -> dict[str, Any]:
    entry = _container().get_skill_catalog().get_skill(skill_id, profile_id=profile_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    return entry.model_dump(mode="json")


@router.put("/skills/{skill_id}")
async def put_skill(
    skill_id: str,
    body: SkillCatalogPut,
    _auth: Annotated[AuthClaims | None, Depends(require_operator_role)] = None,
) -> dict[str, Any]:
    saved = UpsertSkill(_mutation()).execute(
        skill_id,
        body.model_dump(),
        actor=api_actor(_auth),
    )
    return saved.model_dump(mode="json")


@router.post("/skills/{skill_id}/approve")
async def approve_skill(
    skill_id: str,
    profile_id: str = DEFAULT_PROFILE_ID,
    _auth: Annotated[AuthClaims | None, Depends(require_operator_role)] = None,
) -> dict[str, Any]:
    try:
        saved = _mutation().approve_skill(
            skill_id,
            profile_id=profile_id,
            actor=api_actor(_auth),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return saved.model_dump(mode="json")


@router.delete("/skills/{skill_id}")
async def delete_skill(
    skill_id: str,
    profile_id: str = DEFAULT_PROFILE_ID,
    _auth: Annotated[AuthClaims | None, Depends(require_operator_role)] = None,
) -> dict[str, Any]:
    ok = _mutation().delete_skill(
        skill_id,
        profile_id=profile_id,
        actor=api_actor(_auth),
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"deleted": True, "id": skill_id}


@router.get("/plans")
async def list_plans(
    profile_id: str | None = None,
    _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
) -> dict[str, Any]:
    plans = _container().get_plan_catalog().list_plans(profile_id=profile_id, enabled_only=False)
    return {"plans": [plan.model_dump(mode="json") for plan in plans]}


@router.get("/plans/{plan_id}")
async def get_plan(
    plan_id: str,
    profile_id: str = DEFAULT_PROFILE_ID,
    _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
) -> dict[str, Any]:
    entry = _container().get_plan_catalog().get_plan(plan_id, profile_id=profile_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return entry.model_dump(mode="json")


@router.put("/plans/{plan_id}")
async def put_plan(
    plan_id: str,
    body: PlanCatalogPut,
    _auth: Annotated[AuthClaims | None, Depends(require_operator_role)] = None,
) -> dict[str, Any]:
    saved = UpsertPlan(_mutation()).execute(
        plan_id,
        body.model_dump(),
        actor=api_actor(_auth),
    )
    return saved.model_dump(mode="json")


@router.post("/plans/{plan_id}/activate")
async def activate_plan(
    plan_id: str,
    profile_id: str = DEFAULT_PROFILE_ID,
    _auth: Annotated[AuthClaims | None, Depends(require_operator_role)] = None,
) -> dict[str, Any]:
    entry = _container().get_plan_catalog().activate_plan(plan_id, profile_id=profile_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    _container().reload_catalog()
    return entry.model_dump(mode="json")


@router.get("/mcp-servers")
async def list_mcp_servers(
    profile_id: str | None = None,
    _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
) -> dict[str, Any]:
    servers = _container().get_mcp_catalog().list_servers(profile_id=profile_id, enabled_only=False)
    return {"servers": [server.model_dump(mode="json") for server in servers]}


@router.put("/mcp-servers/{server_id}")
async def put_mcp_server(
    server_id: str,
    body: McpServerPut,
    _auth: Annotated[AuthClaims | None, Depends(require_operator_role)] = None,
) -> dict[str, Any]:
    saved = UpsertMcpServer(_mutation()).execute(
        server_id,
        body.model_dump(),
        actor=api_actor(_auth),
    )
    return saved.model_dump(mode="json")


@router.post("/mcp-servers/{server_id}/health-check")
async def mcp_health_check(
    server_id: str,
    profile_id: str = DEFAULT_PROFILE_ID,
    _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
) -> dict[str, Any]:
    entry = _container().get_mcp_catalog().get_server(server_id, profile_id=profile_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="MCP server not found")
    status = "unknown"
    try:
        response = httpx.get(entry.url, timeout=5.0)
        status = "healthy" if response.status_code < 500 else "degraded"
    except Exception:
        status = "unreachable"
    entry.health_status = status
    _container().get_mcp_catalog().upsert_server(entry)
    return {"id": server_id, "health_status": status}


@router.put("/profiles/{profile_id}")
async def put_profile(
    profile_id: str,
    body: ProfilePackPut,
    _auth: Annotated[AuthClaims | None, Depends(require_operator_role)] = None,
) -> dict[str, Any]:
    saved = UpsertProfilePack(
        _container().get_agent_catalog(),
        policy_merge=get_container().get_policy_merge_port(),
        mutation=_mutation(),
        reload=_container().reload_catalog,
    ).execute(
        profile_id,
        body.model_dump(),
        actor=api_actor(_auth),
    )
    return saved.model_dump(mode="json")


@router.get("/profiles/{profile_id}/policy")
async def get_profile_policy(
    profile_id: str,
    _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
) -> dict[str, Any]:
    profiles = _container().get_agent_catalog().list_profiles()
    profile = next((item for item in profiles if item.id == profile_id), None)
    policy = _container().get_profile_policy_port().get_policy(profile_id)
    return {
        "profile_id": profile_id,
        "profile": profile.model_dump(mode="json") if profile else None,
        "policy": policy.model_dump(mode="json"),
    }


@router.put("/profiles/{profile_id}/policy")
async def put_profile_policy(
    profile_id: str,
    body: ProfilePolicyPut,
    _auth: Annotated[AuthClaims | None, Depends(require_operator_role)] = None,
) -> dict[str, Any]:
    policy = UpsertProfilePolicy(
        _container().get_agent_catalog(),
        policy_merge=get_container().get_policy_merge_port(),
        policy_defaults=get_container().get_policy_defaults_port(),
        mutation=_mutation(),
        reload=_container().reload_catalog,
    ).execute(profile_id, body.policy, actor=api_actor(_auth))
    return {"profile_id": profile_id, "policy": policy.model_dump(mode="json")}


@router.get("/tools")
async def list_tools_api(
    profile_id: str | None = None,
    _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
) -> dict[str, Any]:
    tools = _container().get_tool_catalog().list_tools(profile_id=profile_id, enabled_only=False)
    return {"tools": [tool.model_dump(mode="json") for tool in tools]}


@router.get("/tools/{tool_id}")
async def get_tool_api(
    tool_id: str,
    profile_id: str = DEFAULT_PROFILE_ID,
    _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
) -> dict[str, Any]:
    entry = _container().get_tool_catalog().get_tool(tool_id, profile_id=profile_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    return entry.model_dump(mode="json")


@router.put("/tools/{tool_id}")
async def put_tool_api(
    tool_id: str,
    body: ToolCatalogPut,
    _auth: Annotated[AuthClaims | None, Depends(require_operator_role)] = None,
) -> dict[str, Any]:
    saved = UpsertTool(_mutation()).execute(
        tool_id,
        body.model_dump(),
        actor=api_actor(_auth),
    )
    return saved.model_dump(mode="json")


@router.get("/evaluations/{persona}")
async def get_evaluation(
    persona: str,
    _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
) -> dict[str, Any]:
    entry = _container().get_agent_catalog().get_agent(persona)
    if entry is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    return {
        "persona": persona,
        "declared_trust_level": entry.trust_level,
        "quality": entry.quality.model_dump(mode="json"),
    }


@router.get("/evaluations")
async def list_evaluations(
    profile_id: str | None = None,
    _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
) -> dict[str, Any]:
    agents = _container().get_agent_catalog().list_agents(profile_id=profile_id, enabled_only=False)
    leaderboard = sorted(agents, key=lambda item: item.quality.empirical_trust, reverse=True)
    return {
        "evaluations": [
            {
                "persona": entry.name,
                "empirical_trust": entry.quality.empirical_trust,
                "sample_size": entry.quality.sample_size,
                "declared_trust_level": entry.trust_level,
            }
            for entry in leaderboard
        ]
    }


@router.get("/profiles")
async def list_profiles(
    _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
) -> dict[str, Any]:
    catalog = _container().get_agent_catalog()
    profiles = catalog.list_profiles()
    return {"profiles": [p.model_dump() if hasattr(p, "model_dump") else p for p in profiles]}


@router.get("/audit")
async def catalog_audit(
    limit: int = 50,
    _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
) -> dict[str, Any]:
    return {"entries": _container().get_catalog_audit().list_entries(limit=limit)}


@router.post("/reload")
async def reload_catalog(
    _auth: Annotated[AuthClaims | None, Depends(require_operator_role)] = None,
) -> dict[str, Any]:
    _container().reload_catalog()
    return {"reloaded": True, "version": _container().get_catalog_version()}


@router.post("/seed")
async def seed_catalog(
    _auth: Annotated[AuthClaims | None, Depends(require_operator_role)] = None,
) -> dict[str, Any]:
    return _container().get_seed_catalog().execute()
