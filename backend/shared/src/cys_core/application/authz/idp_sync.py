from __future__ import annotations

from dataclasses import dataclass

from cys_core.application.ports.authz import AuthzTuple


@dataclass(frozen=True)
class IdpGroupMapping:
    group: str
    organization_id: str
    relation: str = "member"


def membership_tuples_for_user(
    *,
    user_id: str,
    groups: list[str],
    mappings: list[IdpGroupMapping],
) -> list[AuthzTuple]:
    """Map IdP groups to organization membership/admin tuples only."""
    group_set = {group.strip() for group in groups if group.strip()}
    tuples: list[AuthzTuple] = []
    for mapping in mappings:
        if mapping.group not in group_set:
            continue
        relation = "admin" if mapping.relation == "admin" else "member"
        tuples.append(
            AuthzTuple(
                user=f"user:{user_id}",
                relation=relation,
                object=f"organization:{mapping.organization_id}",
            )
        )
    return tuples


def platform_admin_tuples(*, user_id: str) -> list[AuthzTuple]:
    """Platform admins are explicitly mapped; no datasource grants are inferred."""
    return [
        AuthzTuple(
            user=f"user:{user_id}",
            relation="admin",
            object="organization:platform",
        )
    ]
