from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI

from cys_core.domain.security.auth_models import AuthClaims
from cys_core.observability.http import mount_metrics
from interfaces.gateways.tool.auth import require_gateway_role
from interfaces.gateways.tool.handler import invoke_tool
from interfaces.gateways.tool.models import ToolInvokeRequest, ToolInvokeResponse


def create_app() -> FastAPI:
    app = FastAPI(title="cys-agi MCP Tool Gateway", version="0.1.0")
    mount_metrics(app)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/invoke", response_model=ToolInvokeResponse)
    async def post_invoke(
        request: ToolInvokeRequest,
        _auth: Annotated[AuthClaims | None, Depends(require_gateway_role)],
    ) -> ToolInvokeResponse:
        return invoke_tool(request)

    return app
