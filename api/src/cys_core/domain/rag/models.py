from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from cys_core.domain.security.classification import DataClassification


class ChunkACL(BaseModel):
    tenant: str = "default"
    classification: DataClassification = DataClassification.INTERNAL
    roles: list[str] = Field(default_factory=lambda: ["analyst"])
    owner: str = ""


class DocumentProvenance(BaseModel):
    source_id: str
    source_name: str = ""
    uploaded_by: str = ""
    content_hash: str = ""
    approved: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagChunk(BaseModel):
    chunk_id: str
    text: str
    acl: ChunkACL = Field(default_factory=ChunkACL)
    provenance: DocumentProvenance
    token_estimate: int = 0


class RetrievalResult(BaseModel):
    query: str
    chunks: list[RagChunk] = Field(default_factory=list)
    denied_count: int = 0
    fail_closed: bool = False
    error: str = ""
