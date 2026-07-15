from unittest.mock import MagicMock, patch

from cys_core.registry.agents import AgentRegistry
from cys_core.runtime.agent import AgentRuntime


def test_runtime_builds_agent_from_config():
    registry = AgentRegistry.load()
    runtime = AgentRuntime(registry)
    defn = registry.get("critic")

    with patch("cys_core.runtime.agent.create_agent") as mock_create:
        mock_create.return_value = MagicMock()
        runtime.create(defn, use_checkpointer=False)

    mock_create.assert_called_once()
    kwargs = mock_create.call_args.kwargs
    assert kwargs["name"] == "critic"
    assert kwargs["system_prompt"] == defn.system_prompt
    assert kwargs["tools"] == []
