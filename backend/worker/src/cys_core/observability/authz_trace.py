"""OpenTelemetry attributes for authz decisions."""

from __future__ import annotations


def record_authz_decision(decision: str, *, relation: str = "", object: str = "") -> None:
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span is None or not span.is_recording():
            return
        span.set_attribute("authz_decision", decision)
        if relation:
            span.set_attribute("authz_relation", relation)
        if object:
            span.set_attribute("authz_object", object)
    except Exception:
        return
