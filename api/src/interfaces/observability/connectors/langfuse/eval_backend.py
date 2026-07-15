from __future__ import annotations

from cys_core.domain.observability.models import EvalScore
from cys_core.infrastructure.observability.backends import NoopEvalBackend


class LangfuseEvalBackend(NoopEvalBackend):
    """Record experiment scores to Langfuse when SDK is configured."""

    def record_score(self, trace_id: str, name: str, value: float, *, comment: str = "") -> None:
        try:
            from bootstrap.settings import get_settings
            from langfuse import Langfuse

            settings = get_settings()
            if not settings.langfuse_enabled:
                return
            client = Langfuse(
                public_key=settings.resolved_langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.resolved_langfuse_host,
            )
            client.create_score(trace_id=trace_id, name=name, value=value, comment=comment or None)
        except Exception:
            return

    def run_experiment(self, dataset: str, *, evaluator: str = "default") -> list[EvalScore]:
        _ = evaluator
        return [EvalScore(dataset=dataset, item_id="langfuse", score=0.0, passed=True)]
