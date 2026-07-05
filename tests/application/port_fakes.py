from __future__ import annotations

from types import SimpleNamespace

from cys_core.application.use_cases.analyze_task_hints import AnalyzeTaskHints


def fake_correlation_id_port():
    return SimpleNamespace(bind=lambda _cid: object(), reset=lambda _token: None)


def fake_catalog_seed_loaders(*, skills=None, plans=None, mcp_servers=None):
    return SimpleNamespace(
        load_skills=lambda profile_id: list(skills or []),
        load_plans=lambda profile_id: list(plans or []),
        load_mcp_servers=lambda profile_id: list(mcp_servers or []),
    )


def fake_worker_tracing_port():
    from contextlib import contextmanager

    class _Fake:
        @contextmanager
        def span(self, _name: str, **_attributes):
            yield None

    return _Fake()


def fake_resource_source(personas: list[str] | None = None):
    names = personas or ["soc", "network", "consultant"]
    return SimpleNamespace(list_worker_personas=lambda profile_id=None: list(names))


def fake_persona_ranking():
    return SimpleNamespace(rank=lambda personas, profile_id="cybersec-soc": list(personas))


def fake_agent_catalog(enabled: list[str] | None = None):
    allowed = set(enabled or ["soc", "network", "consultant"])

    def get_agent(name: str):
        if name not in allowed:
            return None
        return SimpleNamespace(
            name=name,
            enabled=True,
            quality=SimpleNamespace(empirical_trust=0.8),
            output_schema=None,
        )

    return SimpleNamespace(get_agent=get_agent, list_agents=lambda **kwargs: [])


def fake_schema_registry():
    return SimpleNamespace(get=lambda name: object())


def fake_policy_port(*, trust_floor: float = 0.5, ema_alpha: float = 0.3):
    return SimpleNamespace(
        get_trust_floor=lambda profile_id: trust_floor,
        get_max_spawn_depth=lambda profile_id: 2,
        get_policy=lambda profile_id: SimpleNamespace(
            quality_signals=SimpleNamespace(
                job_success=0.8,
                job_failure=0.2,
                trace_critic_pass=0.7,
                trace_critic_fail=0.3,
                hitl_pause=0.5,
                bus_failure=0.4,
                ema_alpha=ema_alpha,
            )
        ),
        get_notify_control_severities=lambda profile_id: {"critical", "high"},
    )


def run_step_port_kwargs():
    return {
        "context_summarizer": SimpleNamespace(summarize=lambda **kwargs: "summary"),
        "reflexion_store": SimpleNamespace(
            append=lambda *args, **kwargs: None,
            list_for_investigation=lambda *args, **kwargs: [],
        ),
        "policy_port": fake_policy_port(),
        "task_hints": AnalyzeTaskHints(),
    }


def run_worker_job_port_kwargs():
    return {
        "schema_registry": fake_schema_registry(),
        "agent_catalog": fake_agent_catalog(),
    }


def plan_investigation_port_kwargs(**overrides):
    base = {
        "resource_source": fake_resource_source(),
        "persona_ranking": fake_persona_ranking(),
        "agent_catalog": fake_agent_catalog(),
    }
    base.update(overrides)
    return base
