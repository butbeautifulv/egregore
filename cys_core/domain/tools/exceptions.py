from __future__ import annotations


class ToolChainDepthExceeded(Exception):
    """Raised when sequential high-risk tool chain exceeds policy limit."""
