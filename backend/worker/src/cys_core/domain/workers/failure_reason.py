from __future__ import annotations

from enum import StrEnum

import structlog

from cys_core.domain.security.exceptions import SecurityViolation
from cys_core.domain.workers.exceptions import JobBudgetExceeded

logger = structlog.get_logger(__name__)


class WorkerJobFailureReason(StrEnum):
    TIMEOUT = "timeout"
    TOOL_ERROR = "tool_error"
    TOOL_INVALID_ARGS = "tool_invalid_args"
    GROUNDING_REJECTED = "grounding_rejected"
    SCHEMA_INVALID = "schema_invalid"
    BUDGET_EXCEEDED = "budget_exceeded"
    LLM_ERROR = "llm_error"
    SANDBOX_ERROR = "sandbox_error"
    SECURITY_VIOLATION = "security_violation"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


_PREFIX_REASONS: tuple[tuple[str, WorkerJobFailureReason], ...] = (
    ("ungrounded_finding:", WorkerJobFailureReason.GROUNDING_REJECTED),
    ("tools_not_executed:", WorkerJobFailureReason.TOOL_ERROR),
    ("tool_invalid_args:", WorkerJobFailureReason.TOOL_INVALID_ARGS),
    ("empty_finding", WorkerJobFailureReason.SCHEMA_INVALID),
    ("model_refusal:", WorkerJobFailureReason.LLM_ERROR),
    ("worker_job_timeout", WorkerJobFailureReason.TIMEOUT),
    ("recursion_limit_exhausted", WorkerJobFailureReason.TIMEOUT),
    ("dependency_not_ready:", WorkerJobFailureReason.CANCELLED),
    ("cancelled:", WorkerJobFailureReason.CANCELLED),
)


def classify_worker_failure(
    exc: BaseException | None,
    *,
    error_string: str | None = None,
) -> WorkerJobFailureReason:
    """Map terminal worker failures to a low-cardinality reason enum."""
    err = (error_string if error_string is not None else (str(exc) if exc else "")).strip()
    err_lower = err.lower()

    if isinstance(exc, JobBudgetExceeded):
        return WorkerJobFailureReason.BUDGET_EXCEEDED
    if isinstance(exc, SecurityViolation):
        if "schema" in err_lower or "validation" in err_lower or "guardrail" in err_lower:
            return WorkerJobFailureReason.SCHEMA_INVALID
        return WorkerJobFailureReason.SECURITY_VIOLATION
    if isinstance(exc, TimeoutError):
        return WorkerJobFailureReason.TIMEOUT

    if exc is not None and "sandbox" in type(exc).__name__.lower():
        return WorkerJobFailureReason.SANDBOX_ERROR
    if "sandbox" in err_lower and ("create" in err_lower or "destroy" in err_lower or "failed" in err_lower):
        return WorkerJobFailureReason.SANDBOX_ERROR

    for prefix, reason in _PREFIX_REASONS:
        if err.startswith(prefix) or err_lower.startswith(prefix):
            return reason

    if "recursion limit" in err_lower:
        return WorkerJobFailureReason.TIMEOUT

    if err and err != "unknown":
        logger.warning(
            "worker_failure_unclassified",
            error_class=type(exc).__name__ if exc else "",
            error=err[:240],
        )

    return WorkerJobFailureReason.UNKNOWN
