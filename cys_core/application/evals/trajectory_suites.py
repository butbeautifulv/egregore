from __future__ import annotations

from typing import Any

from cys_core.application.tools.schema_exporter import ToolSchemaExporter


class BfclAdapter:
    """BFCL/Gorilla adapter skeleton.

    For now this just maps tool schemas; full dataset execution is optional heavy suite (P11 nightly).
    """

    def build_functions_payload(self, tools: list[Any]) -> list[dict[str, Any]]:
        exporter = ToolSchemaExporter()
        return [exporter.export_json_schema(t) for t in tools]


class AgentBenchAdapter:
    """AgentBench adapter skeleton (trajectory runner stub)."""

    def run_db_os_lite(self) -> dict[str, Any]:
        return {"status": "not_installed"}


class Tau2Adapter:
    """tau2-bench adapter skeleton."""

    def run_mock_domain(self) -> dict[str, Any]:
        return {"status": "not_installed"}

