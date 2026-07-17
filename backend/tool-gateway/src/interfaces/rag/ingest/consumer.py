from __future__ import annotations

from typing import Any

from cys_core.domain.rag.models import DocumentProvenance
from cys_core.domain.security.classification import DataClassification
from interfaces.rag.ingest.chunker import chunk_document
from interfaces.rag.ingest.scanner import scan_document
from interfaces.rag.store import get_vector_store


async def consume_staging_message(payload: dict[str, Any]) -> dict[str, Any]:
    """Process one staged ingest document."""
    text = str(payload.get("text", ""))
    scan = scan_document(text)
    if not scan.approved:
        return {"status": "rejected", "reason": scan.reason, "hash": scan.content_hash}

    provenance = DocumentProvenance(
        source_id=str(payload.get("source_id", "unknown")),
        source_name=str(payload.get("source_name", "")),
        uploaded_by=str(payload.get("uploaded_by", "")),
        content_hash=scan.content_hash,
        approved=True,
        metadata=dict(payload.get("metadata", {})),
    )
    chunks = chunk_document(
        text,
        provenance=provenance,
        tenant=str(payload.get("tenant", "default")),
        classification=DataClassification(payload.get("classification", DataClassification.INTERNAL)),
        roles=list(payload.get("roles", ["analyst"])),
    )
    count = get_vector_store().upsert(chunks)
    return {"status": "ingested", "chunks": count, "hash": scan.content_hash}
