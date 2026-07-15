from __future__ import annotations

from cys_core.domain.security.auth_models import AuthClaims


def api_actor(auth: AuthClaims | None) -> str:
    """Resolve audit actor id from optional JWT claims."""
    return getattr(auth, "sub", "api") if auth else "api"


def api_actor_context(auth: AuthClaims | None) -> dict[str, str]:
    """Audit context: actor + organization_id when present."""
    if auth is None:
        return {"actor": "api", "organization_id": ""}
    return {
        "actor": auth.sub or "api",
        "organization_id": (auth.organization_id or "").strip(),
    }
