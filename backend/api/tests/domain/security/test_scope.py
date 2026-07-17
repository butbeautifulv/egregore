import pytest

from cys_core.domain.security.scope import ScopePolicy


@pytest.mark.unit
def test_scope_allows_listed_tool():
    policy = ScopePolicy.from_tools({"parse_netflow"})
    assert policy.check_tool("parse_netflow") is None


@pytest.mark.unit
def test_scope_denies_unknown_tool():
    policy = ScopePolicy.from_tools({"parse_netflow"})
    reason = policy.check_tool("execute_command")
    assert reason is not None
    assert "execute_command" in reason


@pytest.mark.unit
def test_scope_denies_blocked_path():
    policy = ScopePolicy.from_tools({"read_file"})
    reason = policy.check_path_arg("file_path", "/etc/app/.env")
    assert reason is not None
    assert ".env" in reason


@pytest.mark.unit
def test_scope_ignores_non_path_keys():
    policy = ScopePolicy.from_tools({"read_file"})
    assert policy.check_path_arg("query", "/etc/.env") is None


@pytest.mark.unit
def test_scope_check_tool_call_combined():
    policy = ScopePolicy.from_tools({"read_file"})
    assert policy.check_tool_call("read_file", {"file_path": "/safe/path"}) is None
    assert policy.check_tool_call("read_file", {"file_path": "/secrets/.env"}) is not None
