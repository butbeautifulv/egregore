from __future__ import annotations

from typing import Any

from bootstrap.settings import Settings

_provider_initialized = False


def _build_resource(settings: Settings, service_name: str) -> Any:
    from opentelemetry.sdk.resources import Resource

    attrs: dict[str, str] = {"service.name": service_name}
    if settings.otel_resource_attributes:
        for part in settings.otel_resource_attributes.split(","):
            piece = part.strip()
            if "=" in piece:
                key, value = piece.split("=", 1)
                attrs[key.strip()] = value.strip()
    if settings.k8s_namespace:
        attrs.setdefault("k8s.namespace.name", settings.k8s_namespace)
    attrs.setdefault("deployment.environment", settings.stage)
    return Resource.create(attrs)


def _build_sampler(settings: Settings) -> Any:
    from opentelemetry.sdk.trace.sampling import (
        ALWAYS_ON,
        ParentBased,
        TraceIdRatioBased,
    )

    name = settings.otel_traces_sampler.lower()
    ratio = settings.otel_traces_sampler_arg
    if name in {"parentbased_traceidratio", "traceidratio"}:
        return ParentBased(TraceIdRatioBased(ratio))
    if name in {"parentbased_always_off", "always_off"}:
        from opentelemetry.sdk.trace.sampling import ALWAYS_OFF

        return ParentBased(ALWAYS_OFF)
    return ParentBased(ALWAYS_ON)


def ensure_tracer_provider(*, settings: Settings, service_name: str) -> None:
    global _provider_initialized
    if _provider_initialized or not settings.otel_enabled:
        return

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(
        resource=_build_resource(settings, service_name),
        sampler=_build_sampler(settings),
    )
    exporter = OTLPSpanExporter(
        endpoint=settings.otel_exporter_endpoint,
        insecure=True,
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _provider_initialized = True


def flush_tracer_provider() -> None:
    try:
        from opentelemetry import trace

        provider = trace.get_tracer_provider()
        force_flush = getattr(provider, "force_flush", None)
        if callable(force_flush):
            force_flush()
    except Exception:
        return
