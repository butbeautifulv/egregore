from __future__ import annotations

from typing import Protocol

from cys_core.domain.evidence.models import EvidenceManifest


class EvidenceManifestPort(Protocol):
    def get_merged_manifest(self, job_id: str) -> EvidenceManifest | None: ...

    def get_persona_manifests(self, investigation_id: str) -> dict[str, EvidenceManifest]: ...
