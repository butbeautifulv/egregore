from __future__ import annotations

import pytest

from cys_core.observability.tracing import (
    bind_correlation_id,
    extract_correlation_id,
    get_correlation_id,
    inject_correlation_headers,
    reset_correlation_id,
    structlog_context,
)


@pytest.mark.unit
def test_correlation_id_contextvar_roundtrip():
    token = bind_correlation_id("corr-123")
    try:
        assert get_correlation_id() == "corr-123"
        headers = inject_correlation_headers()
        assert headers["x-correlation-id"] == "corr-123"
        assert structlog_context()["correlation_id"] == "corr-123"
    finally:
        reset_correlation_id(token)
    assert get_correlation_id() == ""


@pytest.mark.unit
def test_extract_correlation_id_from_headers():
    assert extract_correlation_id({"x-correlation-id": "evt-1"}) == "evt-1"
