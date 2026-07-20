from __future__ import annotations


class ToolChainDepthExceeded(Exception):
    """Raised when sequential high-risk tool chain exceeds policy limit."""


class ScopeViolation(Exception):
    """Raised when a tool call falls outside the calling persona's least-privilege allowlist."""


class SandboxTokenInvalid(Exception):
    """Raised when a tool call's sandbox_token is missing, malformed, expired, or mismatched."""


class HitlRequired(Exception):
    """Raised when a tool call's risk exceeds the persona's auto-approve threshold and no valid
    approval_token for this exact call was presented — docs/MSP_BACKLOG.md §35/§58."""

    def __init__(self, *, risk_level: str, approval_token: str) -> None:
        super().__init__(f"tool call requires human approval (risk={risk_level})")
        self.risk_level = risk_level
        self.approval_token = approval_token
