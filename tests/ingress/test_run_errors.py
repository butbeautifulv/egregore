from __future__ import annotations

import pytest
from fastapi import HTTPException

from cys_core.domain.persistence.exceptions import PersistenceUnavailableError
from interfaces.api.run_errors import raise_run_api_error


@pytest.mark.unit
def test_raise_run_api_error_maps_persistence_unavailable():
    with pytest.raises(HTTPException) as exc_info:
        raise_run_api_error(PersistenceUnavailableError("Postgres persistence unavailable"))
    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == {
        "message": "Postgres persistence unavailable",
        "code": "persistence_unavailable",
    }


@pytest.mark.unit
def test_raise_run_api_error_maps_key_error():
    with pytest.raises(HTTPException) as exc_info:
        raise_run_api_error(KeyError("Unknown tool: spawn_worker"))
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["code"] == "unknown_resource"
