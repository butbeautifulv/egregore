from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class AuthError(Exception):
    """Invalid or missing authentication."""


ROLE_INGRESS = "egregore-ingress"
ROLE_OPERATOR = "egregore-operator"
ROLE_GATEWAY = "egregore-gateway"
ROLE_READER = "egregore-reader"


@dataclass(frozen=True)
class AuthClaims:
    sub: str
    email: str = ""
    roles: tuple[str, ...] = field(default_factory=tuple)
    organization_id: str = ""

    def has_any_role(self, *required: str) -> bool:
        if not required:
            return True
        role_set = set(self.roles)
        return any(role in role_set for role in required)


def extract_roles(claims: dict[str, Any], client_id: str) -> tuple[str, ...]:
    seen: set[str] = set()
    roles: list[str] = []

    def add(role_list: Any) -> None:
        if not isinstance(role_list, list):
            return
        for item in role_list:
            if not isinstance(item, str) or not item or item in seen:
                continue
            seen.add(item)
            roles.append(item)

    realm_access = claims.get("realm_access")
    if isinstance(realm_access, dict):
        add(realm_access.get("roles"))

    resource_access = claims.get("resource_access")
    if isinstance(resource_access, dict):
        client_entry = resource_access.get(client_id)
        if isinstance(client_entry, dict):
            add(client_entry.get("roles"))

    return tuple(roles)


def extract_organization_id(claims: dict[str, Any]) -> str:
    """Prefer custom org claim, then organization, then first org in org list."""
    for key in ("organization_id", "org_id", "org", "tenant_id"):
        value = claims.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    org = claims.get("organization")
    if isinstance(org, str) and org.strip():
        return org.strip()
    if isinstance(org, dict):
        for key in ("id", "name"):
            value = org.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def claims_from_payload(payload: dict[str, Any], *, client_id: str) -> AuthClaims:
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise AuthError("missing subject")
    email = payload.get("email")
    return AuthClaims(
        sub=sub,
        email=email if isinstance(email, str) else "",
        roles=extract_roles(payload, client_id),
        organization_id=extract_organization_id(payload),
    )
