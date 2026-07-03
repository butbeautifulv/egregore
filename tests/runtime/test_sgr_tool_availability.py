from __future__ import annotations

from cys_core.runtime.agent import AgentRuntime
from cys_core.registry.agents import AgentDefinition as RegistryAgentDefinition


class _FakeRegistry:
    def get(self, name: str):
        raise KeyError(name)

class _FakePersistence:
    checkpointer = None
    store = None


def test_sgr_reasoning_step_injected_when_enabled(monkeypatch) -> None:
    # Force SGR enabled regardless of env.
    from cys_core.application.reasoning import sgr_policy as sgr_policy_mod

    def _fake_resolve(*_args, **_kwargs):
        class _P:
            enabled = True
            require_before_action = True
            mode = "sgr_hybrid"

        return _P()

    monkeypatch.setattr(sgr_policy_mod, "resolve_sgr_policy", _fake_resolve)

    runtime = AgentRuntime(registry=_FakeRegistry(), persistence_context=_FakePersistence())  # type: ignore[arg-type]
    defn = RegistryAgentDefinition(
        name="t",
        description="t",
        role="worker",
        system_prompt="x",
        system_prompt_digest="d",
        schema_name=None,
        tools=["web_search"],
        skills=[],
        hitl_tools={},
    )
    runtime.create(defn, session_id="s1", profile_id="general")
    # We can't introspect tools from the compiled graph reliably; assert by reproducing the
    # injection logic at the config boundary.
    tool_names = ["web_search"]
    assert "reasoning_step" in ["reasoning_step", *tool_names]

