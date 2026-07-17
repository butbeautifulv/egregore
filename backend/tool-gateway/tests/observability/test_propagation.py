from __future__ import annotations

from cys_core.observability.tracing import (
    bind_from_carrier,
    get_correlation_id,
    inject_correlation_headers,
    reset_correlation_id,
)


def test_bind_from_carrier_sets_correlation_id():
    token = bind_from_carrier({"x-correlation-id": "eng-abc"})
    try:
        assert get_correlation_id() == "eng-abc"
    finally:
        if token is not None:
            reset_correlation_id(token)


def test_inject_extract_correlation_roundtrip():
    token = bind_from_carrier({"x-correlation-id": "eng-roundtrip"})
    try:
        headers = inject_correlation_headers()
        assert headers.get("x-correlation-id") == "eng-roundtrip"
    finally:
        if token is not None:
            reset_correlation_id(token)
