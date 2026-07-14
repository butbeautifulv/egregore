from __future__ import annotations

from dataclasses import dataclass

from cys_core.domain.workers.exceptions import JobBudgetExceeded

_DEFAULT_COST_PER_1K_TOKENS_USD = 0.003
_cost_per_1k_tokens_usd: float = _DEFAULT_COST_PER_1K_TOKENS_USD
_profile_costs: dict[str, float] = {}


def configure_job_cost(cost_per_1k_tokens_usd: float, *, profile_id: str | None = None) -> None:
    global _cost_per_1k_tokens_usd
    if profile_id:
        _profile_costs[profile_id] = cost_per_1k_tokens_usd
    else:
        _cost_per_1k_tokens_usd = cost_per_1k_tokens_usd


def reset_job_cost() -> None:
    """Restore cost-rate config to defaults — used by JobBudgetTracker.clear_all() so a
    profile-scoped rate set by one job/test can't silently leak into an unrelated one
    (_profile_costs was previously never cleared by clear_all())."""
    global _cost_per_1k_tokens_usd
    _cost_per_1k_tokens_usd = _DEFAULT_COST_PER_1K_TOKENS_USD
    _profile_costs.clear()


def _cost_rate(profile_id: str | None = None) -> float:
    if profile_id and profile_id in _profile_costs:
        return _profile_costs[profile_id]
    return _cost_per_1k_tokens_usd


@dataclass
class JobBudgetState:
    max_tokens: int
    max_cost_usd: float
    max_tool_calls: int
    tokens_used: int = 0
    cost_usd: float = 0.0
    tool_calls: int = 0


class JobBudgetTracker:
    """Per-session DoW counters for worker jobs."""

    _states: dict[str, JobBudgetState] = {}
    _profile_ids: dict[str, str] = {}

    @classmethod
    def configure(
        cls,
        session_id: str,
        *,
        max_tokens: int,
        max_cost_usd: float,
        max_tool_calls: int,
        profile_id: str = "cybersec-soc",
    ) -> None:
        cls._states[session_id] = JobBudgetState(
            max_tokens=max_tokens,
            max_cost_usd=max_cost_usd,
            max_tool_calls=max_tool_calls,
        )
        cls._profile_ids[session_id] = profile_id

    @classmethod
    def get(cls, session_id: str) -> JobBudgetState | None:
        return cls._states.get(session_id)

    @classmethod
    def clear(cls, session_id: str) -> None:
        cls._states.pop(session_id, None)
        cls._profile_ids.pop(session_id, None)

    @classmethod
    def clear_all(cls) -> None:
        cls._states.clear()
        cls._profile_ids.clear()
        reset_job_cost()

    @classmethod
    def check_tool_call(cls, session_id: str) -> None:
        state = cls._states.get(session_id)
        if state is None:
            return
        if state.tool_calls >= state.max_tool_calls:
            raise JobBudgetExceeded(f"Job tool-call budget exceeded ({state.max_tool_calls} max)")

    @classmethod
    def record_tool_call(cls, session_id: str) -> None:
        cls.check_tool_call(session_id)
        state = cls._states.get(session_id)
        if state is None:
            return
        state.tool_calls += 1

    @classmethod
    def record_tokens(cls, session_id: str, tokens: int) -> None:
        state = cls._states.get(session_id)
        if state is None or tokens <= 0:
            return
        state.tokens_used += tokens
        profile_id = cls._profile_ids.get(session_id)
        cost = (tokens / 1000.0) * _cost_rate(profile_id)
        state.cost_usd += cost
        cls._check_limits(session_id, state)

    @classmethod
    def _check_limits(cls, session_id: str, state: JobBudgetState) -> None:
        if state.tokens_used > state.max_tokens:
            raise JobBudgetExceeded(f"Job token budget exceeded ({state.max_tokens} max)")
        if state.cost_usd > state.max_cost_usd:
            raise JobBudgetExceeded(f"Job cost budget exceeded (${state.max_cost_usd:.2f} max)")

    @classmethod
    def estimate_tokens(cls, text: str) -> int:
        return max(1, len(text) // 4)
