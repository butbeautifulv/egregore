from __future__ import annotations


class ToolChainDepthExceeded(Exception):
    """Raised when sequential high-risk tool chain exceeds policy limit."""


class ScopeViolation(Exception):
    """Raised when a tool call falls outside the calling persona's least-privilege allowlist."""
