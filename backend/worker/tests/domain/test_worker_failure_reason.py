from __future__ import annotations

import pytest

from cys_core.domain.security.exceptions import SecurityViolation
from cys_core.domain.workers.exceptions import JobBudgetExceeded
from cys_core.domain.workers.failure_reason import WorkerJobFailureReason, classify_worker_failure


@pytest.mark.unit
@pytest.mark.parametrize(
    ("error", "expected"),
    [
        ("worker_job_timeout", WorkerJobFailureReason.TIMEOUT),
        ("recursion_limit_exhausted", WorkerJobFailureReason.TIMEOUT),
        ("ungrounded_finding:claim without obs_id", WorkerJobFailureReason.GROUNDING_REJECTED),
        ("tools_not_executed:planned JSON only", WorkerJobFailureReason.TOOL_ERROR),
        ("tool_invalid_args:query is required", WorkerJobFailureReason.TOOL_INVALID_ARGS),
        ("empty_finding:summary", WorkerJobFailureReason.SCHEMA_INVALID),
        ("model_refusal:cannot process", WorkerJobFailureReason.LLM_ERROR),
        ("dependency_not_ready:soc", WorkerJobFailureReason.CANCELLED),
    ],
)
def test_classify_worker_failure_prefixes(error: str, expected: WorkerJobFailureReason) -> None:
    assert classify_worker_failure(None, error_string=error) == expected


@pytest.mark.unit
def test_classify_worker_failure_budget_exception() -> None:
    assert classify_worker_failure(JobBudgetExceeded("token budget")) == WorkerJobFailureReason.BUDGET_EXCEEDED


@pytest.mark.unit
def test_classify_worker_failure_security_input() -> None:
    assert (
        classify_worker_failure(SecurityViolation("blocked input"), error_string="blocked input")
        == WorkerJobFailureReason.SECURITY_VIOLATION
    )


@pytest.mark.unit
def test_classify_worker_failure_security_schema() -> None:
    assert (
        classify_worker_failure(SecurityViolation("schema validation failed"), error_string="schema validation failed")
        == WorkerJobFailureReason.SCHEMA_INVALID
    )


@pytest.mark.unit
def test_classify_worker_failure_timeout_exception() -> None:
    assert classify_worker_failure(TimeoutError()) == WorkerJobFailureReason.TIMEOUT


@pytest.mark.unit
def test_classify_worker_failure_unknown() -> None:
    assert classify_worker_failure(RuntimeError("boom"), error_string="boom") == WorkerJobFailureReason.UNKNOWN
