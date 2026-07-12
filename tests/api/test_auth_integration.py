from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.unit
def test_list_work_orders_rejects_tenant_mismatch(auth_settings):
    from interfaces.api.app import create_app

    token = auth_settings["token"](["egregore-reader"])
    payload = __import__("json").loads(
        __import__("base64").urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode()
    )
    payload["organization_id"] = "acme"
    token = (
        __import__("base64")
        .urlsafe_b64encode(__import__("json").dumps(payload).encode())
        .decode()
        .rstrip("=")
    )
    client = TestClient(create_app())
    response = client.get("/v1/work-orders", params={"tenant_id": "other"}, headers=_bearer(token))
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "TENANT_MISMATCH"


@pytest.mark.unit
def test_list_work_orders_accepts_matching_tenant(auth_settings):
    from interfaces.api.app import create_app

    token = auth_settings["token"](["egregore-reader"])
    payload = __import__("json").loads(
        __import__("base64").urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode()
    )
    payload["organization_id"] = "acme"
    token = (
        __import__("base64")
        .urlsafe_b64encode(__import__("json").dumps(payload).encode())
        .decode()
        .rstrip("=")
    )
    client = TestClient(create_app())
    response = client.get("/v1/work-orders", params={"tenant_id": "acme"}, headers=_bearer(token))
    assert response.status_code == 200
