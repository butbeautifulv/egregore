from __future__ import annotations

from cys_core.domain.observability.models import (
    EvalScore,
    JudgeRequest,
    JudgeResult,
    PromptRef,
    ResolvedPrompt,
    TraceContext,
)


class NoopTraceBackend:
    def start_span(self, ctx: TraceContext) -> str:
        _ = ctx
        return ""

    def end_span(self, span_id: str) -> None:
        _ = span_id

    def flush(self) -> None:
        return None

    def shutdown(self) -> None:
        return None


class NoopPromptBackend:
    def resolve(self, ref: PromptRef, *, fallback_text: str = "") -> ResolvedPrompt | None:
        _ = ref, fallback_text
        return None


class NoopJudgeBackend:
    def judge(self, request: JudgeRequest) -> JudgeResult:
        _ = request
        return JudgeResult(score=0.0, verdict="noop", reasoning="judge backend disabled")


class NoopEvalBackend:
    def run_experiment(self, dataset: str, *, evaluator: str = "default") -> list[EvalScore]:
        _ = evaluator
        return [EvalScore(dataset=dataset, item_id="noop", score=0.0, passed=True)]

    def record_score(self, trace_id: str, name: str, value: float, *, comment: str = "") -> None:
        _ = trace_id, name, value, comment
