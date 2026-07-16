"""Eval adapter skeletons (RAGAS, BFCL, AgentBench, τ2) — lazy optional deps."""

from __future__ import annotations

from typing import Any


class RagasAdapterSkeleton:
    def faithfulness(self, answer: str, contexts: list[str]) -> float:
        return 1.0 if answer and contexts else 0.0

    def answer_relevancy(self, question: str, answer: str) -> float:
        return 1.0 if question.split()[:1] and answer else 0.0


class FaithEvalLoader:
    def load_case(self, case_id: str) -> dict[str, Any]:
        return {"id": case_id, "unanswerable": False}


class BfclAdapterSkeleton:
    def map_tool_schema(self, tool_name: str) -> dict[str, Any]:
        return {"name": tool_name, "parameters": {"type": "object", "properties": {}}}


class AgentBenchAdapterSkeleton:
    def db_lite_query(self, sql: str) -> list[dict[str, Any]]:
        return [{"sql": sql, "rows": []}]


class Tau2AdapterSkeleton:
    def mock_domain(self) -> str:
        return "retail-mock"
