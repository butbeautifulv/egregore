from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Forward-ref only: Container is api's or worker's own composition
    # root (whichever installs this sub-container), never a module inside
    # contracts itself.
    from bootstrap.container import Container  # ty: ignore[unresolved-import]


class ObservabilityContainer:
    """Owns metrics/tracing/eval/prompt backend construction and caching."""

    def __init__(self, container: "Container") -> None:
        self._container = container
        self._metrics_port = None
        self._correlation_id_port = None
        self._worker_tracing_port = None
        self._trace_flush_port = None

    @property
    def settings(self):
        return self._container.settings

    def get_metrics_port(self):
        if self._metrics_port is None:
            from cys_core.infrastructure.observability.metrics_adapter import build_metrics_port

            self._metrics_port = build_metrics_port()
        return self._metrics_port

    def get_correlation_id_port(self):
        if self._correlation_id_port is None:
            from cys_core.infrastructure.observability.tracing_adapter import build_correlation_id_port

            self._correlation_id_port = build_correlation_id_port()
        return self._correlation_id_port

    def get_worker_tracing_port(self):
        if self._worker_tracing_port is None:
            from cys_core.infrastructure.observability.worker_tracing_adapter import build_worker_tracing_port

            self._worker_tracing_port = build_worker_tracing_port(self.get_trace_backend)
        return self._worker_tracing_port

    def get_application_tracing_port(self):
        return self.get_worker_tracing_port()

    def get_trace_flush_port(self):
        if self._trace_flush_port is None:
            from cys_core.infrastructure.observability.trace_flush_adapter import build_trace_flush_port

            self._trace_flush_port = build_trace_flush_port()
        return self._trace_flush_port

    def get_trace_backend(self):
        from bootstrap.observability_factory import build_trace_backend, resolve_trace_backend_name

        return build_trace_backend(resolve_trace_backend_name(self.settings), cfg=self.settings)

    def get_prompt_backend(self):
        from bootstrap.observability_factory import build_prompt_backend

        return build_prompt_backend(self.settings.obs_prompt_backend)

    def get_judge_backend(self):
        from bootstrap.observability_factory import build_judge_backend

        name = self.settings.obs_judge_backend
        return build_judge_backend(name)

    def get_eval_backend(self):
        from bootstrap.observability_factory import build_eval_backend

        return build_eval_backend(self.settings.obs_eval_backend)

    def get_prompt_resolver(self):
        from cys_core.application.observability.prompt_resolver import PromptResolver

        return PromptResolver(self.get_prompt_backend())
