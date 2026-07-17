from __future__ import annotations

from typing import Any

from cys_core.application.ports.evidence_manifest import EvidenceManifestPort
from cys_core.domain.evidence.models import EvidenceManifest


def technique_id_from_manifest(manifest: EvidenceManifest | None) -> str | None:
    if manifest is None or not manifest.suggested_mitre_techniques:
        return None
    return manifest.suggested_mitre_techniques[0]


def enrich_technique_id_from_manifest(
    out: dict[str, Any],
    *,
    manifest_lookup: EvidenceManifestPort | None = None,
    job_id: str = "",
) -> None:
    technique_id = out.get("technique_id")
    if isinstance(technique_id, str) and technique_id.strip():
        return
    if not job_id or manifest_lookup is None:
        return
    fallback = technique_id_from_manifest(manifest_lookup.get_merged_manifest(job_id))
    if fallback:
        out["technique_id"] = fallback
