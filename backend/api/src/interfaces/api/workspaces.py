from __future__ import annotations

import asyncio
import re
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from bootstrap.container import get_container
from cys_core.application.authz.audit import log_grant_change
from cys_core.application.authz.tenant_bind import resolve_organization_id
from cys_core.application.ports.authz import AuthzTuple
from cys_core.domain.agents.control import is_control_persona
from cys_core.domain.security.auth_models import AuthClaims
from cys_core.domain.security.system_prompt_assembler import resolve_persona_prompt
from cys_core.domain.workspace.models import Workspace, WorkspaceAgent
from interfaces.api.auth import require_operator_role, require_reader_role
from interfaces.api.authz_deps import require_relation
from interfaces.api.authz_helpers import count_active_jobs_for_workspace, require_workspace_relation
from interfaces.api.errors import control_agent_immutable_http, workspace_active_jobs_http
from interfaces.api.tenant_deps import require_tenant_match_http

router = APIRouter(prefix="/v1", tags=["workspaces"])


class WorkspaceCreateIn(BaseModel):
    id: str = ""
    name: str
    tenant_id: str = "default"
    profile_id: str = "cybersec-soc"


class WorkspacePatchIn(BaseModel):
    name: str | None = None
    profile_id: str | None = None


class WorkspaceOut(BaseModel):
    id: str
    organization_id: str
    name: str
    created_by: str = ""
    profile_id: str = "cybersec-soc"
    soft_deleted: bool = False

    @classmethod
    def from_domain(cls, workspace: Workspace) -> WorkspaceOut:
        return cls(**workspace.model_dump())


class WorkspaceListOut(BaseModel):
    workspaces: list[WorkspaceOut] = Field(default_factory=list)


class WorkspaceAgentUpdateIn(BaseModel):
    persona_prompt: str | None = None
    tools: list[str] | None = None
    skills: list[str] | None = None


class WorkspaceAgentOut(BaseModel):
    workspace_id: str
    name: str
    source_agent: str
    persona_prompt: str = ""
    language: str = "ru"
    tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    description: str = ""

    @classmethod
    def from_domain(cls, agent: WorkspaceAgent) -> WorkspaceAgentOut:
        return cls(**agent.model_dump())


class WorkspaceAgentListOut(BaseModel):
    agents: list[WorkspaceAgentOut] = Field(default_factory=list)


class WorkspaceMemberIn(BaseModel):
    user_id: str
    role: Literal["editor", "viewer"]


class GrantOut(BaseModel):
    workspace_id: str
    datasource_id: str = ""
    user_id: str = ""
    relation: str
    applied: bool = True


def _workspace_store():
    return get_container().get_workspace_store()


def _workspace_or_404(workspace_id: str) -> Workspace:
    workspace = _workspace_store().get(workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="workspace_not_found")
    return workspace


def _actor(auth: AuthClaims | None) -> str:
    if auth is None:
        return "api"
    return auth.sub or auth.email or "api"


def _user_ref(user_id: str) -> str:
    user_id = user_id.strip()
    if user_id.startswith("user:"):
        return user_id
    return f"user:{user_id}"


def _workspace_ref(workspace_id: str) -> str:
    return f"workspace:{workspace_id}"


def _workspace_agent_ref(workspace_id: str, name: str) -> str:
    return f"workspace_agent:{workspace_id}/{name}"


def _datasource_ref(datasource_id: str) -> str:
    return f"datasource:{datasource_id}"


def _default_workspace_id(name: str, organization_id: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", name.strip().lower()).strip("-")
    return f"{organization_id}-{slug or 'workspace'}"


def _control_agent_immutable() -> HTTPException:
    return control_agent_immutable_http()


def _write_authz_tuples(tuples: list[AuthzTuple]) -> None:
    get_container().get_authz_service().write_tuples(tuples)


def _delete_authz_tuples(tuples: list[AuthzTuple]) -> None:
    get_container().get_authz_service().delete_tuples(tuples)


@router.get("/workspaces", response_model=WorkspaceListOut)
async def list_workspaces(
    tenant_id: str | None = None,
    _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
) -> WorkspaceListOut:
    return await asyncio.to_thread(_list_workspaces_impl, tenant_id, _auth)


def _list_workspaces_impl(tenant_id: str | None, _auth: AuthClaims | None) -> WorkspaceListOut:
    organization_id = (
        require_tenant_match_http(_auth, tenant_id)
        if tenant_id is not None
        else resolve_organization_id(_auth)
    )
    authz = get_container().get_authz_service()
    if authz.mode != "off" and _auth is not None:
        user = f"user:{_auth.sub}"
        ids = authz.list_objects(user=user, relation="can_view", object_type="workspace")
        if ids:
            workspaces = [
                ws
                for ws_id in ids
                if (ws := _workspace_store().get(ws_id)) is not None
                and ws.organization_id == organization_id
            ]
            return WorkspaceListOut(workspaces=[WorkspaceOut.from_domain(ws) for ws in workspaces])
    return WorkspaceListOut(
        workspaces=[
            WorkspaceOut.from_domain(workspace)
            for workspace in _workspace_store().list_by_organization(organization_id)
        ]
    )


@router.post("/workspaces", response_model=WorkspaceOut)
async def create_workspace(
    body: WorkspaceCreateIn,
    _auth: Annotated[AuthClaims | None, Depends(require_operator_role)] = None,
) -> WorkspaceOut:
    return await asyncio.to_thread(_create_workspace_impl, body, _auth)


def _create_workspace_impl(body: WorkspaceCreateIn, _auth: AuthClaims | None) -> WorkspaceOut:
    organization_id = require_tenant_match_http(_auth, body.tenant_id)
    workspace_id = body.id.strip() or _default_workspace_id(body.name, organization_id)
    workspace = Workspace(
        id=workspace_id,
        organization_id=organization_id,
        name=body.name,
        created_by=_actor(_auth),
        profile_id=body.profile_id,
    )
    saved = _workspace_store().create(workspace)
    _write_authz_tuples(
        [
            AuthzTuple(
                user=f"organization:{organization_id}",
                relation="organization",
                object=_workspace_ref(saved.id),
            ),
            AuthzTuple(
                user=_user_ref(saved.created_by),
                relation="owner",
                object=_workspace_ref(saved.id),
            ),
        ]
    )
    return WorkspaceOut.from_domain(saved)


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceOut)
async def get_workspace(
    workspace_id: str,
    _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
    _authz: Annotated[None, Depends(require_relation("workspace", "can_view", "workspace_id"))] = None,
) -> WorkspaceOut:
    return await asyncio.to_thread(_get_workspace_impl, workspace_id, _auth)


def _get_workspace_impl(workspace_id: str, _auth: AuthClaims | None) -> WorkspaceOut:
    workspace = _workspace_or_404(workspace_id)
    require_tenant_match_http(_auth, workspace.organization_id)
    return WorkspaceOut.from_domain(workspace)


@router.patch("/workspaces/{workspace_id}", response_model=WorkspaceOut)
async def patch_workspace(
    workspace_id: str,
    body: WorkspacePatchIn,
    _auth: Annotated[AuthClaims | None, Depends(require_operator_role)] = None,
    _authz: Annotated[None, Depends(require_relation("workspace", "can_edit", "workspace_id"))] = None,
) -> WorkspaceOut:
    return await asyncio.to_thread(_patch_workspace_impl, workspace_id, body, _auth)


def _patch_workspace_impl(workspace_id: str, body: WorkspacePatchIn, _auth: AuthClaims | None) -> WorkspaceOut:
    workspace = _workspace_or_404(workspace_id)
    require_tenant_match_http(_auth, workspace.organization_id)
    updates = body.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] is not None:
        workspace.name = updates["name"]
    if "profile_id" in updates and updates["profile_id"] is not None:
        workspace.profile_id = updates["profile_id"]
    return WorkspaceOut.from_domain(_workspace_store().update(workspace))


@router.delete("/workspaces/{workspace_id}")
async def delete_workspace(
    workspace_id: str,
    _auth: Annotated[AuthClaims | None, Depends(require_operator_role)] = None,
    _authz: Annotated[None, Depends(require_relation("workspace", "can_edit", "workspace_id"))] = None,
) -> dict[str, str | bool]:
    return await asyncio.to_thread(_delete_workspace_impl, workspace_id, _auth)


def _delete_workspace_impl(workspace_id: str, _auth: AuthClaims | None) -> dict[str, str | bool]:
    workspace = _workspace_or_404(workspace_id)
    require_tenant_match_http(_auth, workspace.organization_id)
    active_jobs = count_active_jobs_for_workspace(workspace.organization_id, workspace_id)
    if active_jobs > 0:
        raise workspace_active_jobs_http(count=active_jobs)
    ok = _workspace_store().soft_delete(workspace_id)
    if ok:
        _delete_authz_tuples(
            [
                AuthzTuple(
                    user=f"organization:{workspace.organization_id}",
                    relation="organization",
                    object=_workspace_ref(workspace_id),
                ),
            ]
        )
        for agent in _workspace_store().list_agents(workspace_id):
            _delete_authz_tuples(
                [
                    AuthzTuple(
                        user=_workspace_ref(workspace_id),
                        relation="workspace",
                        object=_workspace_agent_ref(workspace_id, agent.name),
                    )
                ]
            )
    return {"deleted": ok, "id": workspace_id}


@router.get("/workspaces/{workspace_id}/agents", response_model=WorkspaceAgentListOut)
async def list_workspace_agents(
    workspace_id: str,
    _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
) -> WorkspaceAgentListOut:
    return await asyncio.to_thread(_list_workspace_agents_impl, workspace_id, _auth)


def _list_workspace_agents_impl(workspace_id: str, _auth: AuthClaims | None) -> WorkspaceAgentListOut:
    workspace = _workspace_or_404(workspace_id)
    require_tenant_match_http(_auth, workspace.organization_id)
    return WorkspaceAgentListOut(
        agents=[
            WorkspaceAgentOut.from_domain(agent)
            for agent in _workspace_store().list_agents(workspace_id)
        ]
    )


@router.post("/workspaces/{workspace_id}/agents/{name}/fork", response_model=WorkspaceAgentOut)
async def fork_workspace_agent(
    workspace_id: str,
    name: str,
    _auth: Annotated[AuthClaims | None, Depends(require_operator_role)] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> WorkspaceAgentOut:
    return await asyncio.to_thread(_fork_workspace_agent_impl, workspace_id, name, _auth, authorization)


def _fork_workspace_agent_impl(
    workspace_id: str, name: str, _auth: AuthClaims | None, authorization: str | None
) -> WorkspaceAgentOut:
    if is_control_persona(name):
        raise _control_agent_immutable()
    workspace = _workspace_or_404(workspace_id)
    require_tenant_match_http(_auth, workspace.organization_id)
    require_workspace_relation(_auth, authorization, workspace_id, "can_create_agent")
    entry = get_container().get_agent_catalog().get_agent(name)
    if entry is None:
        raise HTTPException(status_code=404, detail="agent_not_found")
    agent = WorkspaceAgent(
        workspace_id=workspace_id,
        name=name,
        source_agent=name,
        persona_prompt=resolve_persona_prompt(entry),
        language=entry.language,
        tools=list(entry.tools),
        skills=list(entry.skills),
        description=entry.description,
    )
    saved = _workspace_store().upsert_agent(agent)
    _write_authz_tuples(
        [
            AuthzTuple(
                user=_workspace_ref(workspace_id),
                relation="workspace",
                object=_workspace_agent_ref(workspace_id, name),
            )
        ]
    )
    return WorkspaceAgentOut.from_domain(saved)


@router.put("/workspaces/{workspace_id}/agents/{name}", response_model=WorkspaceAgentOut)
async def put_workspace_agent(
    workspace_id: str,
    name: str,
    body: WorkspaceAgentUpdateIn,
    _auth: Annotated[AuthClaims | None, Depends(require_operator_role)] = None,
    _authz: Annotated[None, Depends(require_relation("workspace", "can_edit", "workspace_id"))] = None,
) -> WorkspaceAgentOut:
    return await asyncio.to_thread(_put_workspace_agent_impl, workspace_id, name, body, _auth)


def _put_workspace_agent_impl(
    workspace_id: str, name: str, body: WorkspaceAgentUpdateIn, _auth: AuthClaims | None
) -> WorkspaceAgentOut:
    if is_control_persona(name):
        raise _control_agent_immutable()
    workspace = _workspace_or_404(workspace_id)
    require_tenant_match_http(_auth, workspace.organization_id)
    agent = _workspace_store().get_agent(workspace_id, name)
    if agent is None:
        raise HTTPException(status_code=404, detail="workspace_agent_not_found")
    updates = body.model_dump(exclude_unset=True)
    if updates and "persona_prompt" in updates and updates["persona_prompt"] is not None:
        from cys_core.domain.security.exceptions import SecurityViolation
        from cys_core.domain.security.factory import get_input_sanitizer
        from cys_core.domain.security.sanitizer import InjectionVerdict
        from cys_core.domain.security.system_prompt_assembler import extract_persona_prompt

        candidate = extract_persona_prompt(str(updates["persona_prompt"]))
        verdict = get_input_sanitizer().classify(candidate)
        if verdict is InjectionVerdict.HARD:
            raise SecurityViolation("Prompt injection detected in workspace persona")
        agent.persona_prompt = get_input_sanitizer().filter_patterns(candidate)
    if "tools" in updates and updates["tools"] is not None:
        agent.tools = list(updates["tools"])
    if "skills" in updates and updates["skills"] is not None:
        agent.skills = list(updates["skills"])
    return WorkspaceAgentOut.from_domain(_workspace_store().upsert_agent(agent))


@router.post("/workspaces/{workspace_id}/members", response_model=GrantOut)
async def add_workspace_member(
    workspace_id: str,
    body: WorkspaceMemberIn,
    _auth: Annotated[AuthClaims | None, Depends(require_operator_role)] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> GrantOut:
    return await asyncio.to_thread(_add_workspace_member_impl, workspace_id, body, _auth, authorization)


def _add_workspace_member_impl(
    workspace_id: str, body: WorkspaceMemberIn, _auth: AuthClaims | None, authorization: str | None
) -> GrantOut:
    workspace = _workspace_or_404(workspace_id)
    require_tenant_match_http(_auth, workspace.organization_id)
    require_workspace_relation(_auth, authorization, workspace_id, "can_admin")
    _write_authz_tuples(
        [
            AuthzTuple(
                user=_user_ref(body.user_id),
                relation=body.role,
                object=_workspace_ref(workspace_id),
            )
        ]
    )
    log_grant_change(
        action="invite",
        workspace_id=workspace_id,
        actor=_actor(_auth),
        relation=body.role,
        target=body.user_id,
        organization_id=workspace.organization_id,
    )
    return GrantOut(workspace_id=workspace_id, user_id=body.user_id, relation=body.role)


@router.post("/workspaces/{workspace_id}/datasources/{ds_id}/grant", response_model=GrantOut)
async def grant_workspace_datasource(
    workspace_id: str,
    ds_id: str,
    _auth: Annotated[AuthClaims | None, Depends(require_operator_role)] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> GrantOut:
    return await asyncio.to_thread(_grant_workspace_datasource_impl, workspace_id, ds_id, _auth, authorization)


def _grant_workspace_datasource_impl(
    workspace_id: str, ds_id: str, _auth: AuthClaims | None, authorization: str | None
) -> GrantOut:
    workspace = _workspace_or_404(workspace_id)
    require_tenant_match_http(_auth, workspace.organization_id)
    require_workspace_relation(_auth, authorization, workspace_id, "can_admin")
    _write_authz_tuples(
        [
            AuthzTuple(
                user=_workspace_ref(workspace_id),
                relation="consumer",
                object=_datasource_ref(ds_id),
            )
        ]
    )
    log_grant_change(
        action="grant",
        workspace_id=workspace_id,
        actor=_actor(_auth),
        relation="consumer",
        target=ds_id,
        organization_id=workspace.organization_id,
    )
    return GrantOut(workspace_id=workspace_id, datasource_id=ds_id, relation="consumer")


@router.post("/workspaces/{workspace_id}/datasources/{ds_id}/revoke", response_model=GrantOut)
async def revoke_workspace_datasource(
    workspace_id: str,
    ds_id: str,
    _auth: Annotated[AuthClaims | None, Depends(require_operator_role)] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> GrantOut:
    return await asyncio.to_thread(_revoke_workspace_datasource_impl, workspace_id, ds_id, _auth, authorization)


def _revoke_workspace_datasource_impl(
    workspace_id: str, ds_id: str, _auth: AuthClaims | None, authorization: str | None
) -> GrantOut:
    workspace = _workspace_or_404(workspace_id)
    require_tenant_match_http(_auth, workspace.organization_id)
    require_workspace_relation(_auth, authorization, workspace_id, "can_admin")
    _delete_authz_tuples(
        [
            AuthzTuple(
                user=_workspace_ref(workspace_id),
                relation="consumer",
                object=_datasource_ref(ds_id),
            )
        ]
    )
    log_grant_change(
        action="revoke",
        workspace_id=workspace_id,
        actor=_actor(_auth),
        relation="consumer",
        target=ds_id,
        organization_id=workspace.organization_id,
    )
    return GrantOut(workspace_id=workspace_id, datasource_id=ds_id, relation="consumer")
