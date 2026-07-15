from __future__ import annotations

from cys_core.application.use_cases.analyze_task_hints import AnalyzeTaskHints
from cys_core.application.use_cases.evaluate_trace_critic import EvaluateTraceCritic
from cys_core.domain.observability.models import JudgeRequest, JudgeResult


class _Judge:
    def judge(self, request: JudgeRequest) -> JudgeResult:
        return JudgeResult(score=0.3, verdict="fail", reasoning="mock low score")


def test_analyze_task_hints_heuristic():
    hints = AnalyzeTaskHints().execute("Investigate suspicious IP 10.0.0.5 with encoded powershell")
    assert hints
    assert any("time" in h.lower() or "powershell" in h.lower() for h in hints)


def test_evaluate_trace_critic_heuristic():
    verdict = EvaluateTraceCritic().execute(goal="test", trace={"reply": "ok"}, step_count=1)
    assert 0.0 <= verdict.score <= 1.0


def test_evaluate_trace_critic_with_judge():
    verdict = EvaluateTraceCritic(judge_backend=_Judge(), threshold=0.55).execute(
        goal="goal",
        trace="spawn worker without result",
        step_count=3,
    )
    assert verdict.should_rerun is True
