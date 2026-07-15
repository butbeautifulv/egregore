from __future__ import annotations

from bootstrap.settings import Settings, get_settings, settings
from cys_core.application.ports.observability.eval_backend import EvalBackendPort
from cys_core.application.ports.observability.judge_backend import JudgeBackendPort
from cys_core.application.ports.observability.prompt_backend import PromptBackendPort
from cys_core.application.ports.observability.trace_backend import TraceBackendPort
from cys_core.infrastructure.observability.backends import (
    NoopEvalBackend,
    NoopJudgeBackend,
    NoopPromptBackend,
    NoopTraceBackend,
)


def resolve_trace_backend_name(cfg: Settings | None = None) -> str:
    cfg = cfg or get_settings()
    if cfg.otel_enabled and cfg.obs_trace_backend in ("langfuse", "composite"):
        return "composite"
    return cfg.obs_trace_backend


def build_trace_backend(
    name: str,
    *,
    cfg: Settings | None = None,
    service_name: str | None = None,
) -> TraceBackendPort:
    cfg = cfg or settings
    if name == "noop":
        return NoopTraceBackend()
    if name == "langfuse":
        from interfaces.observability.connectors.langfuse.trace import LangfuseTraceBackend

        return LangfuseTraceBackend()
    if name == "otel":
        from interfaces.observability.connectors.otel.trace import OtelTraceBackend

        return OtelTraceBackend(service_name=service_name)
    if name == "composite":
        from interfaces.observability.connectors.langfuse.trace import CompositeTraceBackend, LangfuseTraceBackend
        from interfaces.observability.connectors.otel.trace import OtelTraceBackend

        sinks: list[TraceBackendPort] = [LangfuseTraceBackend()]
        if cfg.otel_enabled:
            sinks.append(OtelTraceBackend(service_name=service_name))
        return CompositeTraceBackend(*sinks)
    return NoopTraceBackend()


def build_prompt_backend(name: str) -> PromptBackendPort:
    if name == "noop":
        return NoopPromptBackend()
    if name == "filesystem":
        from interfaces.observability.connectors.filesystem.prompt import FilesystemPromptBackend

        return FilesystemPromptBackend()
    if name == "langfuse":
        from interfaces.observability.connectors.langfuse.prompt import LangfusePromptBackend

        return LangfusePromptBackend()
    return NoopPromptBackend()


def build_judge_backend(name: str) -> JudgeBackendPort:
    if name == "noop":
        return NoopJudgeBackend()
    if name == "langfuse":
        from interfaces.observability.connectors.langfuse.judge import LangfuseJudgeBackend

        return LangfuseJudgeBackend()
    return NoopJudgeBackend()


def build_eval_backend(name: str) -> EvalBackendPort:
    if name == "noop":
        return NoopEvalBackend()
    if name == "langfuse":
        from interfaces.observability.connectors.langfuse.eval_backend import LangfuseEvalBackend

        return LangfuseEvalBackend()
    return NoopEvalBackend()
