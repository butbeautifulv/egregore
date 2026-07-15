from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from cys_core.domain.evidence.models import EvidenceManifest


class EvidenceSnapshot(BaseModel):
    """Frozen evidence state for revision and follow-up continuation."""

    investigation_id: str
    tenant_id: str = "default"
    persona_manifests: dict[str, EvidenceManifest] = Field(default_factory=dict)
    merged_manifest: EvidenceManifest | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def primary_manifest(self) -> EvidenceManifest | None:
        if self.merged_manifest is not None:
            return self.merged_manifest
        if not self.persona_manifests:
            return None
        return next(iter(self.persona_manifests.values()))
