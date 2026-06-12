from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

A2A_PROTOCOL_VERSION = "a2a/1.0"


class MtlsPeerIdentity(BaseModel):
    """mTLS peer identity pinned to an agent."""

    subject: str
    san: str | None = None
    required: bool = True


class A2AEnvelope(BaseModel):
    """Minimal Agent-to-Agent message envelope."""

    protocol: Literal["a2a/1.0"] = A2A_PROTOCOL_VERSION
    sender: str
    recipient: str
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: str
    signature: str
    mtls: dict[str, Any]


def default_mtls_subject(agent_id: str) -> str:
    return f"spiffe://cys-agi/agent/{agent_id}"
