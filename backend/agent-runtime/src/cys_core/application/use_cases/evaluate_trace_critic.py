from __future__ import annotations

import json
from typing import Any

from cys_core.application.ports.observability.judge_backend import JudgeBackendPort
from cys_core.application.ports.trace_callbacks import get_trace_callbacks
from cys_core.application.ports.tracing_ports import NOOP_APPLICATION_TRACING, ApplicationTracingPort
from cys_core.domain.observability.models import JudgeRequest, PromptRef
from cys_core.domain.runs.trace_models import TraceVerdict


class EvaluateTraceCritic:
    """Doubter-lite: critique action trace before synthesis (DeepAgent doubter pattern)."""

    def __init__(
        self,
        *,
        judge_backend: JudgeBackendPort | None = None,
        threshold: float = 0.55,
        application_tracing: ApplicationTracingPort | None = None,
    ) -> None:
        self.judge_backend = judge_backend
        self.threshold = threshold
        self._tracing = application_tracing or NOOP_APPLICATION_TRACING

    def execute(
        self,
        *,
        goal: str,
        trace: dict[str, Any] | list[Any] | str,
        step_count: int = 0,
        engagement_id: str = "",
    ) -> TraceVerdict:
        with self._tracing.span("run.trace_critic", engagement_id=engagement_id, step_count=step_count):
            return self._execute_inner(goal=goal, trace=trace, step_count=step_count)

    def _execute_inner(
        self,
        *,
        goal: str,
        trace: dict[str, Any] | list[Any] | str,
        step_count: int = 0,
    ) -> TraceVerdict:
        trace_text = trace if isinstance(trace, str) else json.dumps(trace, ensure_ascii=False, default=str)
        issues = _heuristic_issues(trace_text)
        base_score = max(0.2, 0.9 - 0.15 * len(issues))

        if self.judge_backend is not None:
            result = self.judge_backend.judge(
                JudgeRequest(
                    rubric_ref=PromptRef(name="trace-critic"),
                    input_text=goal,
                    output_text=trace_text[:8000],
                    context={"step_count": step_count},
                )
            )
            score = min(base_score, result.score) if result.score > 0 else base_score
            if result.verdict == "fail" or score < self.threshold:
                issues.append(result.reasoning or "judge flagged trace")
            return TraceVerdict(
                score=score,
                verdict=result.verdict or ("pass" if score >= self.threshold else "fail"),
                reasoning=result.reasoning,
                should_rerun=score < self.threshold,
                issues=issues,
            )

        llm_verdict = self._reasoning_judge(goal, trace_text, step_count)
        if llm_verdict is not None:
            if llm_verdict.issues:
                llm_verdict.issues.extend(issues)
            else:
                llm_verdict.issues = issues
            return llm_verdict

        should_rerun = base_score < self.threshold
        return TraceVerdict(
            score=base_score,
            verdict="pass" if not should_rerun else "fail",
            reasoning="heuristic trace evaluation",
            should_rerun=should_rerun,
            issues=issues,
        )

    def _reasoning_judge(self, goal: str, trace_text: str, step_count: int) -> TraceVerdict | None:
        try:
            from cys_core.application.runtime_config import get_reasoning_llm_settings, get_trace_critic_use_reasoning

            if not get_trace_critic_use_reasoning() or not str(get_reasoning_llm_settings().get("model", "")).strip():
                return None
            from cys_core.domain.workers.job_budget import JobBudgetTracker
            from cys_core.llm.reasoning import get_reasoning_model_connector

            session_key = f"judge:trace:{step_count}"
            JobBudgetTracker.record_tokens(session_key, JobBudgetTracker.estimate_tokens(trace_text[:4000]))
            model = get_reasoning_model_connector().create_model()
            prompt = (
                f"Rate trace quality for goal: {goal}\n"
                f"Trace:\n{trace_text[:6000]}\n"
                "Reply JSON: {\"score\":0.0-1.0,\"verdict\":\"pass|fail\",\"reasoning\":\"...\"}"
            )
            response = model.invoke(prompt, config={"callbacks": get_trace_callbacks()})
            text = str(getattr(response, "content", response))
            data = json.loads(text[text.find("{") : text.rfind("}") + 1]) if "{" in text else {}
            score = float(data.get("score", 0.5))
            verdict = str(data.get("verdict", "pass" if score >= self.threshold else "fail"))
            return TraceVerdict(
                score=score,
                verdict=verdict,
                reasoning=str(data.get("reasoning", "")),
                should_rerun=score < self.threshold,
                issues=[],
            )
        except Exception:
            return None


def _heuristic_issues(trace_text: str) -> list[str]:
    issues: list[str] = []
    lower = trace_text.lower()
    if "error" in lower and "stub" in lower:
        issues.append("trace contains tool errors or stub responses")
    if "spawn" in lower and "result" not in lower:
        issues.append("spawn requested without visible spawn_result")
    if len(trace_text) < 40:
        issues.append("trace too short to verify reasoning")
    return issues
