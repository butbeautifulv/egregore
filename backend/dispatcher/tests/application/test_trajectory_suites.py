from __future__ import annotations

from langchain_core.tools import tool

from cys_core.application.evals.trajectory_suites import BfclAdapter


@tool
def foo(x: int) -> str:
    """Toy tool for schema export test."""
    return str(x)


def test_bfcl_adapter_exports_tool_schema() -> None:
    payload = BfclAdapter().build_functions_payload([foo])
    assert payload[0]["name"] == "foo"

