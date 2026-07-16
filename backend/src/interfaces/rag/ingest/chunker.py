from __future__ import annotations

import uuid

from cys_core.domain.rag.models import ChunkACL, DocumentProvenance, RagChunk
from cys_core.domain.security.classification import DataClassification, SecureContextBuilder


def chunk_document(
    text: str,
    *,
    provenance: DocumentProvenance,
    tenant: str = "default",
    classification: DataClassification = DataClassification.INTERNAL,
    roles: list[str] | None = None,
    max_chars: int = 1200,
) -> list[RagChunk]:
    """Split document text into ACL-tagged chunks."""
    roles = roles or ["analyst"]
    builder = SecureContextBuilder(tenant=tenant, roles=roles)
    effective_class = classification
    detected = builder.classify_text(text)
    if _class_order_index(detected) > _class_order_index(effective_class):
        effective_class = detected

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text.strip()] if text.strip() else []

    chunks: list[RagChunk] = []
    buffer = ""
    for paragraph in paragraphs:
        candidate = f"{buffer}\n\n{paragraph}".strip() if buffer else paragraph
        if len(candidate) > max_chars and buffer:
            chunks.append(_make_chunk(buffer, provenance, tenant, effective_class, roles))
            buffer = paragraph
        else:
            buffer = candidate
    if buffer:
        chunks.append(_make_chunk(buffer, provenance, tenant, effective_class, roles))
    return chunks


def _class_order_index(level: DataClassification) -> int:
    order = [
        DataClassification.PUBLIC,
        DataClassification.INTERNAL,
        DataClassification.CONFIDENTIAL,
        DataClassification.RESTRICTED,
    ]
    return order.index(level)


def _make_chunk(
    text: str,
    provenance: DocumentProvenance,
    tenant: str,
    classification: DataClassification,
    roles: list[str],
) -> RagChunk:
    return RagChunk(
        chunk_id=f"chunk-{uuid.uuid4().hex[:12]}",
        text=text,
        acl=ChunkACL(tenant=tenant, classification=classification, roles=roles, owner=provenance.uploaded_by),
        provenance=provenance,
        token_estimate=max(1, len(text) // 4),
    )
