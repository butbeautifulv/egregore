from __future__ import annotations

from cys_core.application.tools.registry_provider import get_default_tool_provider
from cys_core.domain.tools.models import ToolDefinitionView


def render_tool_matrix_markdown(*, profile_ids: list[str] | None = None) -> str:
    profiles = profile_ids or ["cybersec-soc", "general-assistant", "gaia-benchmark"]
    provider = get_default_tool_provider()
    lines = [
        "# Tool matrix (generated)",
        "",
        "Auto-generated from `ToolProviderPort` metadata. Regenerate: `scripts/generate_tool_matrix.py`.",
        "",
    ]
    for profile_id in profiles:
        definitions = provider.definitions(profile_id=profile_id)
        lines.append(f"## Profile: `{profile_id}`")
        lines.append("")
        lines.append("| Tool | Module | Status | Datasource | Description |")
        lines.append("|------|--------|--------|------------|-------------|")
        for item in _sorted_definitions(definitions):
            lines.append(_row(item))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _sorted_definitions(definitions: list[ToolDefinitionView]) -> list[ToolDefinitionView]:
    return sorted(definitions, key=lambda item: (item.module, item.name))


def _row(item: ToolDefinitionView) -> str:
    ds = item.datasource_id or "—"
    desc = (item.description or "").replace("|", "\\|")
    return f"| `{item.name}` | {item.module} | {item.status.value} | {ds} | {desc} |"
