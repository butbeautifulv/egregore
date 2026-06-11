from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DirectedAcyclicGraph:
    nodes: tuple[str, ...]
    edges: tuple[tuple[str, str], ...]

    def topological_order(self) -> list[str]:
        incoming = {node: 0 for node in self.nodes}
        outgoing: dict[str, list[str]] = {node: [] for node in self.nodes}
        for source, target in self.edges:
            if source not in incoming or target not in incoming:
                raise ValueError(f"Unknown DAG node in edge: {source} -> {target}")
            incoming[target] += 1
            outgoing[source].append(target)

        ready = [node for node in self.nodes if incoming[node] == 0]
        ordered: list[str] = []
        while ready:
            node = ready.pop(0)
            ordered.append(node)
            for target in outgoing[node]:
                incoming[target] -= 1
                if incoming[target] == 0:
                    ready.append(target)

        if len(ordered) != len(self.nodes):
            raise ValueError("Graph contains a cycle")
        return ordered

    def validate_acyclic(self) -> None:
        self.topological_order()


def assessment_dag() -> DirectedAcyclicGraph:
    return DirectedAcyclicGraph(
        nodes=("ingest", "run_agent", "critic", "hitl_gate", "report"),
        edges=(
            ("ingest", "run_agent"),
            ("run_agent", "critic"),
            ("critic", "hitl_gate"),
            ("hitl_gate", "report"),
        ),
    )

