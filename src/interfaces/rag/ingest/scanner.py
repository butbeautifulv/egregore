from __future__ import annotations

import hashlib

from pydantic import BaseModel

from cys_core.domain.security.exceptions import SecurityViolation
from cys_core.domain.security.factory import get_input_sanitizer
from cys_core.domain.security.sanitizer import InputSanitizer


class IngestScanResult(BaseModel):
    content_hash: str
    approved: bool
    verdict: str = "clean"
    reason: str = ""


def compute_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def scan_document(text: str, sanitizer: InputSanitizer | None = None) -> IngestScanResult:
    """Hash + injection scan before staging/ingest."""
    san = sanitizer or get_input_sanitizer()
    content_hash = compute_content_hash(text)
    verdict = san.classify(text)
    if verdict.value == "hard":
        return IngestScanResult(
            content_hash=content_hash,
            approved=False,
            verdict=verdict.value,
            reason="hard injection detected at ingest",
        )
    try:
        san.sanitize(text, source="external")
    except SecurityViolation as exc:
        return IngestScanResult(
            content_hash=content_hash,
            approved=False,
            verdict="hard",
            reason=str(exc),
        )
    return IngestScanResult(content_hash=content_hash, approved=True, verdict=verdict.value)
