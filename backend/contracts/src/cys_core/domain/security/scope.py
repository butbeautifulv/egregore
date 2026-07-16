from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScopePolicy:
    """Least-privilege tool and path access rules."""

    allowed_tools: frozenset[str]
    blocked_path_patterns: tuple[str, ...] = (
        "*.env",
        "*.key",
        "*.pem",
        "*secret*",
    )

    @classmethod
    def from_tools(
        cls,
        allowed_tools: set[str] | frozenset[str],
        blocked_path_patterns: list[str] | None = None,
    ) -> ScopePolicy:
        patterns = tuple(blocked_path_patterns) if blocked_path_patterns is not None else cls.blocked_path_patterns
        return cls(allowed_tools=frozenset(allowed_tools), blocked_path_patterns=patterns)

    def check_tool(self, tool_name: str) -> str | None:
        if tool_name not in self.allowed_tools:
            return f"Access denied: tool '{tool_name}' is not allowed for this agent."
        return None

    def check_path_arg(self, key: str, value: str) -> str | None:
        if "path" not in key.lower():
            return None
        lower = value.lower()
        for pattern in self.blocked_path_patterns:
            clean = pattern.replace("*", "")
            if clean and clean in lower:
                return f"Access denied: path '{value}' matches blocked pattern."
        return None

    def check_tool_call(self, tool_name: str, args: dict) -> str | None:
        if (reason := self.check_tool(tool_name)) is not None:
            return reason
        for key, value in args.items():
            if isinstance(value, str):
                if (reason := self.check_path_arg(key, value)) is not None:
                    return reason
        return None
