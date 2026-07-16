from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

MemorySource = Literal["user", "agent", "rag", "tool", "eval"]
MemoryDomain = Literal["soc", "general", "gaia", "unknown"]


class MemoryRecord(BaseModel):
    """Eval-native memory unit with provenance and ACL hints."""

    id: str = Field(default_factory=lambda: f"mrec-{uuid4().hex[:12]}")
    content: str
    source: MemorySource = "agent"
    domain: MemoryDomain = "unknown"
    tenant_id: str = "default"
    persona: str = ""
    acl_roles: list[str] = Field(default_factory=list)
    classification: str = "internal"
    chunk_ids: list[str] = Field(default_factory=list)
    source_span: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    meta: dict[str, Any] = Field(default_factory=dict)


class RetrievalContext(BaseModel):
    """RAG retrieval provenance for eval and trace."""

    query: str
    chunk_ids: list[str] = Field(default_factory=list)
    source_spans: list[str] = Field(default_factory=list)
    denied_doc_ids: list[str] = Field(default_factory=list)
    contexts: list[dict[str, Any]] = Field(default_factory=list)


class RagQueryResult(BaseModel):
    """Separate answer from retrieved contexts (eval export friendly)."""

    query: str
    contexts: RetrievalContext
    answer: str = ""
    citations: list[str] = Field(default_factory=list)
