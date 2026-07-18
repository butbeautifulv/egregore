from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any, TypedDict

from cys_core.application.catalog_singletons import rebind_catalog_singletons_if_needed
from cys_core.domain.reasoning.sgr_models import SgrMode


def normalize_sgr_mode(mode: str) -> SgrMode:
    """Map env aliases (soft/iron) to domain SgrMode.

    Lives here (not cys_core.application.reasoning.sgr_tooling, which is
    worker-only per the api/worker split) because configure_from_settings()
    below calls it unconditionally during every Container's __init__ — both
    api's and worker's. sgr_tooling.py re-exports this same function for
    backwards-compat call sites within worker.
    """
    key = (mode or "off").lower().strip()
    if key in {"soft", "sgr_hybrid", "hybrid"}:
        return "sgr_hybrid"
    if key in {"iron", "sgr_iron"}:
        return "sgr_iron"
    if key in {"off", "sgr_off"}:
        return "off"
    return "off"


class LlmSettings(TypedDict):
    model: str
    api_key: str
    base_url: str | None
    temperature: float
    request_timeout: float
    thinking_token_budget: int
    num_retries: int

_POLICY_GETTER_DEPRECATION = (
    "Policy getters in runtime_config are deprecated; use "
    "get_profile_policy_resolver() from cys_core.application.policy_resolver"
)

_stage: str = "dev"
_engagement_async_planning: bool = True
_use_conductor_for_events: bool = False
_max_spawn_depth: int = 5
_use_dynamic_catalog: bool = True
_use_memory_fallback: bool = False
_postgres_url: str = ""
_default_job_recursion_limit: int = 25
_triage_recursion_limit: int = 22
_llm_model: str = "anthropic/claude-sonnet-4"
_llm_api_key: str = ""
_llm_base_url: str | None = None
_llm_temperature: float = 0.1
_llm_request_timeout: float = 120.0
_llm_thinking_token_budget: int = 0
_llm_num_retries: int = 2
_veil_mcp_url: str = "http://localhost:8091/mcp"
_veil_mcp_enabled: bool = True
_veil_mcp_timeout: float = 30.0
_siem_mcp_url: str = "http://localhost:8094/mcp"
_siem_mcp_enabled: bool = False
_siem_mcp_timeout: float = 180.0
_nessus_mcp_url: str = "http://localhost:8095/mcp"
_nessus_mcp_enabled: bool = False
_nessus_mcp_timeout: float = 180.0
_veneno_mcp_url: str = "http://localhost:8093/mcp"
_veneno_mcp_enabled: bool = False
_veneno_mcp_timeout: float = 60.0
_planner_fallback_personas: str = "consultant"
_max_planner_personas: int = 6
_planner_default_execution_mode: str = "parallel"
_egregore_one_tool_per_turn: bool = True
_egregore_json_tool_call_fallback: bool = True
_egregore_strict_plan: bool = False
_stream_agent_output: bool = False
_stream_agent_tools: bool = True
_stream_agent_token_streaming: bool = False
_keep_tool_results: int = 3
_search_judge_llm: bool = False
_self_consistency_n: int = 0
_self_refine_max: int = 0
_browser_enabled: bool = False
_perplexity_api_key: str = ""
_jina_api_key: str = ""
_delegate_budget_fraction: float = 0.35
_trace_critic_enabled: bool = True
_trace_critic_threshold: float = 0.55
_trace_critic_every_n_steps: int = 3
_context_summary_max_messages: int = 40
_task_hints_enabled: bool = True
_web_search_provider: str = "duckduckgo"
_serper_api_key: str = ""
_run_attachments_dir: str = "/tmp/egregore-attachments"
_context_summary_enabled: bool = True
_trace_critic_rerun_max: int = 2
_trace_critic_hitl_on_exhausted: bool = True
_reasoning_model: str = ""
_reasoning_temperature: float = 0.0
_trace_critic_use_reasoning: bool = False
_e2b_api_key: str = ""
_python_sandbox_timeout: float = 30.0
_python_sandbox_image: str = "python:3.12-slim"
_use_sgr_reasoning: bool = True
_sgr_default_mode: str = "off"
_sgr_iron_max_retries: int = 3
_use_run_kernel: bool = False
_budget_use_api_usage: bool = True
_runtime_configured: bool = False
_bus_seen_ttl_seconds: int = 300
_planner_default_post_processors: str = "advisory_consultant_fallback,staged_soc_intel_for_incident"
_follow_up_enabled: bool = True
_follow_up_plan_enabled: bool = True
_follow_up_conversation_query_limit: int = 200
_max_follow_ups_per_engagement: int = 10
_max_follow_up_plans_per_engagement: int = 3
_follow_up_history_limit: int = 100
_follow_up_aggregator_timeout_s: float = 300.0
_follow_up_aggregator_poll_s: float = 2.0
_follow_up_merge_query_limit: int = 30
_follow_up_merge_summary_max: int = 400
_tool_output_preview_max: int = 16_384
_tool_stored_outputs_max: int = 5
_tool_siem_drilldown_max: int = 2
_timeout_salvage_summary_max: int = 2000
_critic_trust_threshold: float = 0.5
_critic_default_confidence: float = 0.5
_worker_max_attempts: int = 3
_worker_triage_max_attempts: int = 2
_web_search_default_limit: int = 5
_duckduckgo_api_url: str = "https://api.duckduckgo.com/"
_duckduckgo_api_timeout_s: float = 15.0
_serper_api_url: str = "https://google.serper.dev/search"
_serper_api_timeout_s: float = 20.0


def configure_from_settings(settings: Any) -> None:
    global _runtime_configured
    global _stage, _engagement_async_planning, _use_conductor_for_events
    global _max_spawn_depth, _use_dynamic_catalog, _use_memory_fallback
    global _postgres_url, _default_job_recursion_limit, _triage_recursion_limit
    global _llm_model, _llm_api_key, _llm_base_url, _llm_temperature, _llm_request_timeout
    global _llm_thinking_token_budget, _llm_num_retries
    global _veil_mcp_url, _veil_mcp_enabled, _veil_mcp_timeout
    global _siem_mcp_url, _siem_mcp_enabled, _siem_mcp_timeout
    global _nessus_mcp_url, _nessus_mcp_enabled, _nessus_mcp_timeout
    global _veneno_mcp_url, _veneno_mcp_enabled, _veneno_mcp_timeout, _planner_fallback_personas
    global _max_planner_personas, _planner_default_execution_mode
    global _egregore_one_tool_per_turn, _egregore_json_tool_call_fallback
    global _trace_critic_enabled, _trace_critic_threshold
    global _trace_critic_every_n_steps, _context_summary_max_messages, _task_hints_enabled
    global _web_search_provider, _serper_api_key, _run_attachments_dir
    global _context_summary_enabled, _trace_critic_rerun_max, _trace_critic_hitl_on_exhausted
    global _reasoning_model, _reasoning_temperature, _e2b_api_key, _python_sandbox_timeout, _python_sandbox_image
    global _egregore_strict_plan, _keep_tool_results, _search_judge_llm, _self_consistency_n
    global _stream_agent_output, _stream_agent_tools, _stream_agent_token_streaming
    global _self_refine_max, _browser_enabled, _perplexity_api_key, _jina_api_key, _delegate_budget_fraction
    global _trace_critic_use_reasoning
    global _use_sgr_reasoning, _sgr_default_mode, _sgr_iron_max_retries, _use_run_kernel, _budget_use_api_usage
    global _bus_seen_ttl_seconds, _planner_default_post_processors
    global _follow_up_enabled, _follow_up_plan_enabled, _follow_up_conversation_query_limit
    global _max_follow_ups_per_engagement, _max_follow_up_plans_per_engagement, _follow_up_history_limit
    global _follow_up_aggregator_timeout_s, _follow_up_aggregator_poll_s
    global _follow_up_merge_query_limit, _follow_up_merge_summary_max
    global _tool_output_preview_max, _tool_stored_outputs_max, _tool_siem_drilldown_max
    global _timeout_salvage_summary_max, _critic_trust_threshold, _critic_default_confidence
    global _worker_max_attempts, _worker_triage_max_attempts
    global _web_search_default_limit, _duckduckgo_api_url, _duckduckgo_api_timeout_s
    global _serper_api_url, _serper_api_timeout_s
    prev_use_postgres = _use_dynamic_catalog and not _use_memory_fallback
    _stage = settings.stage
    _engagement_async_planning = settings.engagement_async_planning
    _use_conductor_for_events = settings.use_conductor_for_events
    _max_spawn_depth = settings.max_spawn_depth
    _use_dynamic_catalog = settings.use_dynamic_catalog
    _use_memory_fallback = settings.use_memory_fallback
    _postgres_url = settings.postgres_url
    _default_job_recursion_limit = settings.default_job_recursion_limit
    _triage_recursion_limit = settings.triage_recursion_limit
    _llm_model = settings.llm_model
    _llm_api_key = settings.llm_api_key
    _llm_base_url = settings.llm_base_url
    _llm_temperature = settings.llm_temperature
    _llm_request_timeout = settings.llm_request_timeout
    _llm_thinking_token_budget = settings.llm_thinking_token_budget
    _llm_num_retries = settings.llm_num_retries
    _veil_mcp_url = settings.veil_mcp_url
    _veil_mcp_enabled = settings.veil_mcp_enabled
    _veil_mcp_timeout = settings.veil_mcp_timeout
    _siem_mcp_url = settings.siem_mcp_url
    _siem_mcp_enabled = settings.siem_mcp_enabled
    _siem_mcp_timeout = settings.siem_mcp_timeout
    _nessus_mcp_url = settings.nessus_mcp_url
    _nessus_mcp_enabled = settings.nessus_mcp_enabled
    _nessus_mcp_timeout = settings.nessus_mcp_timeout
    _veneno_mcp_url = settings.veneno_mcp_url
    _veneno_mcp_enabled = settings.veneno_mcp_enabled
    _veneno_mcp_timeout = settings.veneno_mcp_timeout
    _planner_fallback_personas = settings.planner_fallback_personas
    _max_planner_personas = settings.max_planner_personas
    _planner_default_execution_mode = settings.planner_default_execution_mode
    _egregore_one_tool_per_turn = settings.egregore_one_tool_per_turn
    _egregore_json_tool_call_fallback = settings.egregore_json_tool_call_fallback
    _egregore_strict_plan = settings.egregore_strict_plan
    _stream_agent_output = settings.stream_agent_output
    _stream_agent_tools = settings.stream_agent_tools
    _stream_agent_token_streaming = settings.stream_agent_token_streaming
    _keep_tool_results = settings.keep_tool_results
    _search_judge_llm = settings.search_judge_llm
    _self_consistency_n = settings.self_consistency_n
    _self_refine_max = settings.self_refine_max
    _browser_enabled = settings.browser_enabled
    _perplexity_api_key = settings.perplexity_api_key
    _jina_api_key = settings.jina_api_key
    _delegate_budget_fraction = settings.delegate_budget_fraction
    _trace_critic_enabled = settings.trace_critic_enabled
    _trace_critic_threshold = settings.trace_critic_threshold
    _trace_critic_every_n_steps = settings.trace_critic_every_n_steps
    _context_summary_max_messages = settings.context_summary_max_messages
    _task_hints_enabled = settings.task_hints_enabled
    _web_search_provider = settings.web_search_provider
    _serper_api_key = settings.serper_api_key
    _run_attachments_dir = settings.run_attachments_dir
    _context_summary_enabled = settings.context_summary_enabled
    _trace_critic_rerun_max = settings.trace_critic_rerun_max
    _trace_critic_hitl_on_exhausted = settings.trace_critic_hitl_on_exhausted
    _reasoning_model = settings.reasoning_model
    _reasoning_temperature = settings.reasoning_temperature
    _trace_critic_use_reasoning = settings.trace_critic_use_reasoning
    _e2b_api_key = settings.e2b_api_key
    _python_sandbox_timeout = settings.python_sandbox_timeout
    _python_sandbox_image = settings.python_sandbox_image
    _use_sgr_reasoning = settings.use_sgr_reasoning
    _sgr_default_mode = normalize_sgr_mode(settings.sgr_default_mode)
    _sgr_iron_max_retries = settings.sgr_iron_max_retries
    _use_run_kernel = getattr(settings, "use_run_kernel", False)
    _budget_use_api_usage = settings.budget_use_api_usage
    _bus_seen_ttl_seconds = settings.bus_seen_ttl_seconds
    _planner_default_post_processors = settings.planner_default_post_processors
    _follow_up_enabled = settings.follow_up_enabled
    _follow_up_plan_enabled = settings.follow_up_plan_enabled
    _follow_up_conversation_query_limit = settings.follow_up_conversation_query_limit
    _max_follow_ups_per_engagement = settings.max_follow_ups_per_engagement
    _max_follow_up_plans_per_engagement = settings.max_follow_up_plans_per_engagement
    _follow_up_history_limit = settings.follow_up_history_limit
    _follow_up_aggregator_timeout_s = settings.follow_up_aggregator_timeout_s
    _follow_up_aggregator_poll_s = settings.follow_up_aggregator_poll_s
    _follow_up_merge_query_limit = settings.follow_up_merge_query_limit
    _follow_up_merge_summary_max = settings.follow_up_merge_summary_max
    _tool_output_preview_max = settings.tool_output_preview_max
    _tool_stored_outputs_max = settings.tool_stored_outputs_max
    _tool_siem_drilldown_max = settings.tool_siem_drilldown_max
    _timeout_salvage_summary_max = settings.timeout_salvage_summary_max
    _critic_trust_threshold = settings.critic_trust_threshold
    _critic_default_confidence = settings.critic_default_confidence
    _worker_max_attempts = settings.worker_max_attempts
    _worker_triage_max_attempts = settings.worker_triage_max_attempts
    _web_search_default_limit = settings.web_search_default_limit
    _duckduckgo_api_url = settings.duckduckgo_api_url
    _duckduckgo_api_timeout_s = settings.duckduckgo_api_timeout_s
    _serper_api_url = settings.serper_api_url
    _serper_api_timeout_s = settings.serper_api_timeout_s
    rebind_catalog_singletons_if_needed(
        prev_use_postgres=prev_use_postgres,
        new_use_postgres=_use_dynamic_catalog and not _use_memory_fallback,
    )
    _runtime_configured = True


def is_runtime_configured() -> bool:
    return _runtime_configured


def get_stage() -> str:
    return _stage


def get_engagement_async_planning() -> bool:
    return _engagement_async_planning


def get_use_conductor_for_events() -> bool:
    return _use_conductor_for_events


def get_max_spawn_depth(profile_id: str | None = None) -> int:
    warnings.warn(_POLICY_GETTER_DEPRECATION, DeprecationWarning, stacklevel=2)
    from cys_core.application.policy_resolver import get_profile_policy_resolver
    from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID

    pid = profile_id or DEFAULT_PROFILE_ID
    return get_profile_policy_resolver().max_spawn_depth(pid)


def get_use_dynamic_catalog() -> bool:
    return _use_dynamic_catalog


def get_use_memory_fallback() -> bool:
    return _use_memory_fallback


def get_postgres_url() -> str:
    return _postgres_url


def get_default_job_recursion_limit() -> int:
    return _default_job_recursion_limit


def get_triage_recursion_limit() -> int:
    return _triage_recursion_limit


_TRIAGE_PERSONAS = frozenset({"soc", "intel"})


def get_recursion_limit_for_persona(persona: str) -> int:
    if persona in _TRIAGE_PERSONAS:
        return _triage_recursion_limit
    return _default_job_recursion_limit


def get_llm_settings() -> LlmSettings:
    return {
        "model": _llm_model,
        "api_key": _llm_api_key,
        "base_url": _llm_base_url,
        "temperature": _llm_temperature,
        "request_timeout": _llm_request_timeout,
        "thinking_token_budget": _llm_thinking_token_budget,
        "num_retries": _llm_num_retries,
    }


def veil_mcp_enabled() -> bool:
    return _veil_mcp_enabled


def get_veil_mcp_url() -> str:
    return _veil_mcp_url


def get_veil_mcp_timeout() -> float:
    return _veil_mcp_timeout


def siem_mcp_enabled() -> bool:
    return _siem_mcp_enabled


def get_siem_mcp_url() -> str:
    return _siem_mcp_url


def get_siem_mcp_timeout() -> float:
    return _siem_mcp_timeout


def nessus_mcp_enabled() -> bool:
    return _nessus_mcp_enabled


def get_nessus_mcp_url() -> str:
    return _nessus_mcp_url


def get_nessus_mcp_timeout() -> float:
    return _nessus_mcp_timeout


def veneno_mcp_enabled() -> bool:
    return _veneno_mcp_enabled


def get_veneno_mcp_url() -> str:
    return _veneno_mcp_url


def get_veneno_mcp_timeout() -> float:
    return _veneno_mcp_timeout


def get_planner_fallback_personas() -> str:
    warnings.warn(_POLICY_GETTER_DEPRECATION, DeprecationWarning, stacklevel=2)
    return _planner_fallback_personas


def get_max_planner_personas() -> int:
    return _max_planner_personas


def get_planner_default_execution_mode() -> str:
    return _planner_default_execution_mode


def get_egregore_one_tool_per_turn() -> bool:
    return _egregore_one_tool_per_turn


def get_egregore_json_tool_call_fallback() -> bool:
    return _egregore_json_tool_call_fallback


def get_use_sgr_reasoning() -> bool:
    return _use_sgr_reasoning


def get_sgr_default_mode() -> str:
    return _sgr_default_mode


def get_sgr_iron_max_retries() -> int:
    return _sgr_iron_max_retries


def get_trace_critic_enabled() -> bool:
    return _trace_critic_enabled


def get_trace_critic_threshold() -> float:
    warnings.warn(_POLICY_GETTER_DEPRECATION, DeprecationWarning, stacklevel=2)
    from cys_core.application.policy_resolver import get_profile_policy_resolver
    from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID

    return get_profile_policy_resolver().trace_critic_threshold(DEFAULT_PROFILE_ID)


def get_trace_critic_every_n_steps() -> int:
    warnings.warn(_POLICY_GETTER_DEPRECATION, DeprecationWarning, stacklevel=2)
    from cys_core.application.policy_resolver import get_profile_policy_resolver
    from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID

    return get_profile_policy_resolver().trace_critic_every_n(DEFAULT_PROFILE_ID)


def get_context_summary_max_messages() -> int:
    return _context_summary_max_messages


def get_task_hints_enabled() -> bool:
    return _task_hints_enabled


def get_web_search_provider() -> str:
    return _web_search_provider


def get_serper_api_key() -> str:
    return _serper_api_key


def get_run_attachments_dir() -> str:
    return _run_attachments_dir


def get_context_summary_enabled() -> bool:
    return _context_summary_enabled


def get_trace_critic_rerun_max() -> int:
    warnings.warn(_POLICY_GETTER_DEPRECATION, DeprecationWarning, stacklevel=2)
    from cys_core.application.policy_resolver import get_profile_policy_resolver
    from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID

    return get_profile_policy_resolver().trace_critic_rerun_max(DEFAULT_PROFILE_ID)


def get_trace_critic_hitl_on_exhausted() -> bool:
    return _trace_critic_hitl_on_exhausted


def get_reasoning_llm_settings() -> LlmSettings:
    model = _reasoning_model or _llm_model
    return {
        "model": model,
        "api_key": _llm_api_key,
        "base_url": _llm_base_url,
        "temperature": _reasoning_temperature,
        "request_timeout": _llm_request_timeout,
        "thinking_token_budget": _llm_thinking_token_budget,
        "num_retries": _llm_num_retries,
    }


def get_trace_critic_use_reasoning() -> bool:
    return _trace_critic_use_reasoning


def get_e2b_api_key() -> str:
    return _e2b_api_key


def get_python_sandbox_timeout() -> float:
    return _python_sandbox_timeout


def get_python_sandbox_image() -> str:
    return _python_sandbox_image


def get_egregore_strict_plan() -> bool:
    return _egregore_strict_plan


def get_stream_agent_output() -> bool:
    return _stream_agent_output


def get_stream_agent_tools() -> bool:
    return _stream_agent_output and _stream_agent_tools


def get_stream_agent_token_streaming() -> bool:
    return _stream_agent_output and _stream_agent_token_streaming


def get_keep_tool_results() -> int:
    return _keep_tool_results


def get_search_judge_llm() -> bool:
    return _search_judge_llm


def get_self_consistency_n() -> int:
    return _self_consistency_n


def get_self_refine_max() -> int:
    return _self_refine_max


def get_browser_enabled() -> bool:
    return _browser_enabled


def get_perplexity_api_key() -> str:
    return _perplexity_api_key


def get_jina_api_key() -> str:
    return _jina_api_key


def get_delegate_budget_fraction() -> float:
    warnings.warn(_POLICY_GETTER_DEPRECATION, DeprecationWarning, stacklevel=2)
    from cys_core.application.policy_resolver import get_profile_policy_resolver
    from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID

    return get_profile_policy_resolver().delegate_budget_fraction(DEFAULT_PROFILE_ID)


def get_use_run_kernel() -> bool:
    return _use_run_kernel


def get_budget_use_api_usage() -> bool:
    return _budget_use_api_usage


@dataclass(frozen=True)
class FollowUpSettings:
    follow_up_enabled: bool
    follow_up_conversation_query_limit: int
    max_follow_ups_per_engagement: int
    max_follow_up_plans_per_engagement: int
    follow_up_history_limit: int


def get_bus_seen_ttl_seconds() -> int:
    return _bus_seen_ttl_seconds


def get_planner_default_post_processors() -> str:
    return _planner_default_post_processors


def get_follow_up_settings() -> FollowUpSettings:
    return FollowUpSettings(
        follow_up_enabled=_follow_up_enabled,
        follow_up_conversation_query_limit=_follow_up_conversation_query_limit,
        max_follow_ups_per_engagement=_max_follow_ups_per_engagement,
        max_follow_up_plans_per_engagement=_max_follow_up_plans_per_engagement,
        follow_up_history_limit=_follow_up_history_limit,
    )


def get_follow_up_plan_enabled() -> bool:
    return _follow_up_plan_enabled


def get_follow_up_aggregator_timeout_s() -> float:
    return _follow_up_aggregator_timeout_s


def get_follow_up_aggregator_poll_s() -> float:
    return _follow_up_aggregator_poll_s


def get_follow_up_merge_query_limit() -> int:
    return _follow_up_merge_query_limit


def get_follow_up_merge_summary_max() -> int:
    return _follow_up_merge_summary_max


def get_tool_output_preview_max() -> int:
    return _tool_output_preview_max


def get_tool_stored_outputs_max() -> int:
    return _tool_stored_outputs_max


def get_tool_siem_drilldown_max() -> int:
    return _tool_siem_drilldown_max


def get_timeout_salvage_summary_max() -> int:
    return _timeout_salvage_summary_max


def get_critic_trust_threshold() -> float:
    return _critic_trust_threshold


def get_critic_default_confidence() -> float:
    return _critic_default_confidence


def get_worker_max_attempts() -> int:
    return _worker_max_attempts


def get_worker_triage_max_attempts() -> int:
    return _worker_triage_max_attempts


def get_web_search_default_limit() -> int:
    return _web_search_default_limit


def get_duckduckgo_api_url() -> str:
    return _duckduckgo_api_url


def get_duckduckgo_api_timeout_s() -> float:
    return _duckduckgo_api_timeout_s


def get_serper_api_url() -> str:
    return _serper_api_url


def get_serper_api_timeout_s() -> float:
    return _serper_api_timeout_s
