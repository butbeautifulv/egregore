from __future__ import annotations

import threading
from typing import Any

from cys_core.domain.evidence.manifest_builder import build_manifest_from_tool_output, merge_manifests
from cys_core.domain.evidence.models import EvidenceManifest
from cys_core.domain.parsing.json_text import parse_json_text

_lock = threading.Lock()
_counts: dict[str, int] = {}
_successes: dict[str, set[str]] = {}
_outputs: dict[str, list[tuple[str, str]]] = {}
_manifests: dict[str, list[EvidenceManifest]] = {}
_persona_manifests: dict[str, dict[str, EvidenceManifest]] = {}

_veil_counts: dict[str, int] = {}
_siem_drilldown_counts: dict[str, int] = {}

_MAX_OUTPUT_PREVIEW = 16_384
_MAX_STORED_OUTPUTS = 5
_MAX_SIEM_DRILLDOWN = 2


def record_tool_execution(job_id: str) -> None:
    if not job_id:
        return
    with _lock:
        _counts[job_id] = _counts.get(job_id, 0) + 1


def get_tool_execution_count(job_id: str) -> int:
    if not job_id:
        return 0
    with _lock:
        return _counts.get(job_id, 0)


def clear_tool_execution_count(job_id: str) -> None:
    if not job_id:
        return
    with _lock:
        _counts.pop(job_id, None)
        _successes.pop(job_id, None)
        _outputs.pop(job_id, None)
        _manifests.pop(job_id, None)
        _veil_counts.pop(job_id, None)
        _siem_drilldown_counts.pop(job_id, None)
        from cys_core.application.workers.tool_result_cache import clear_tool_result_cache
        from cys_core.middleware.tool_dedup_middleware import clear_tool_dedup

        clear_tool_result_cache(job_id)
        clear_tool_dedup(job_id)


def record_tool_success(job_id: str, tool_name: str) -> None:
    if not job_id or not tool_name:
        return
    with _lock:
        _successes.setdefault(job_id, set()).add(tool_name)


def tool_succeeded(job_id: str, tool_name: str) -> bool:
    if not job_id or not tool_name:
        return False
    with _lock:
        return tool_name in _successes.get(job_id, set())


def record_tool_output(job_id: str, tool_name: str, preview: str) -> None:
    if not job_id or not tool_name:
        return
    text = (preview or "").strip()
    if not text:
        return
    if len(text) > _MAX_OUTPUT_PREVIEW:
        text = text[:_MAX_OUTPUT_PREVIEW] + "…"
    with _lock:
        entries = _outputs.setdefault(job_id, [])
        entries.append((tool_name, text))
        if len(entries) > _MAX_STORED_OUTPUTS:
            del entries[: len(entries) - _MAX_STORED_OUTPUTS]


def get_tool_outputs(job_id: str) -> list[tuple[str, str]]:
    if not job_id:
        return []
    with _lock:
        return list(_outputs.get(job_id, []))


def _parse_tool_payload(preview: str) -> dict[str, Any] | None:
    payload = parse_json_text(preview)
    if not isinstance(payload, dict):
        return None
    content = payload.get("content", payload)
    if isinstance(content, str):
        parsed = parse_json_text(content)
        content = parsed if isinstance(parsed, dict) else None
    if isinstance(content, dict):
        return content
    return None


class TrackerManifestAdapter:
    """In-memory EvidenceManifestPort backed by module-level tracker state."""

    def get_merged_manifest(self, job_id: str) -> EvidenceManifest | None:
        return get_merged_manifest(job_id)

    def get_persona_manifests(self, investigation_id: str) -> dict[str, EvidenceManifest]:
        return get_persona_manifests(investigation_id)


def get_manifest_port() -> TrackerManifestAdapter:
    return TrackerManifestAdapter()


def record_evidence_manifest(job_id: str, tool_name: str, manifest: EvidenceManifest) -> None:
    if not job_id:
        return
    with _lock:
        entries = _manifests.setdefault(job_id, [])
        entries.append(manifest)


def get_merged_manifest(job_id: str) -> EvidenceManifest | None:
    if not job_id:
        return None
    with _lock:
        entries = _manifests.get(job_id, [])
    if not entries:
        return None
    return merge_manifests(*entries)


def record_persona_manifest(investigation_id: str, persona: str, manifest: EvidenceManifest) -> None:
    if not investigation_id or not persona:
        return
    with _lock:
        bucket = _persona_manifests.setdefault(investigation_id, {})
        existing = bucket.get(persona)
        bucket[persona] = merge_manifests(existing, manifest) if existing else manifest


def get_persona_manifests(investigation_id: str) -> dict[str, EvidenceManifest]:
    if not investigation_id:
        return {}
    with _lock:
        return dict(_persona_manifests.get(investigation_id, {}))


def hydrate_job_from_snapshot(job_id: str, snapshot) -> None:
    """Seed in-memory tool/evidence state from a frozen snapshot."""
    from cys_core.domain.evidence.snapshot import EvidenceSnapshot

    if not job_id or snapshot is None:
        return
    model = snapshot if isinstance(snapshot, EvidenceSnapshot) else EvidenceSnapshot.model_validate(snapshot)
    for persona, manifest in model.persona_manifests.items():
        record_persona_manifest(model.investigation_id, persona, manifest)
    primary = model.primary_manifest()
    if primary is not None:
        seed_job_from_persona_manifest(job_id, primary)


def seed_job_from_persona_manifest(
    job_id: str,
    manifest: EvidenceManifest,
    *,
    mark_siem_done: bool = True,
) -> None:
    if not job_id or manifest is None:
        return
    record_evidence_manifest(job_id, "investigate_incident", manifest)
    if mark_siem_done and (manifest.observations or manifest.telemetry_level != "metadata_only"):
        record_tool_success(job_id, "investigate_incident")


def siem_investigate_done(job_id: str, investigation_id: str = "", *, persona: str = "soc") -> bool:
    if tool_succeeded(job_id, "investigate_incident"):
        return True
    if not investigation_id:
        return False
    manifests = get_persona_manifests(investigation_id)
    if manifests.get(persona) is not None:
        return True
    if persona != "soc" and manifests.get("soc") is not None:
        return True
    return False


def record_siem_drilldown(job_id: str) -> None:
    if not job_id:
        return
    with _lock:
        _siem_drilldown_counts[job_id] = _siem_drilldown_counts.get(job_id, 0) + 1


def siem_drilldown_budget_exhausted(job_id: str) -> bool:
    if not job_id:
        return True
    with _lock:
        return _siem_drilldown_counts.get(job_id, 0) >= _MAX_SIEM_DRILLDOWN


def is_siem_telemetry_sparse(job_id: str) -> bool:
    manifest = get_merged_manifest(job_id)
    if manifest is None:
        return False
    return manifest.telemetry_level != "rich"


def ingest_tool_output_manifest(job_id: str, tool_name: str, preview: str) -> EvidenceManifest | None:
    payload = _parse_tool_payload(preview)
    if payload is None:
        return None
    if tool_name == "investigate_incident" and isinstance(payload.get("evidence_manifest"), dict):
        try:
            embedded = EvidenceManifest.model_validate(payload["evidence_manifest"])
            rebuilt = build_manifest_from_tool_output(tool_name, payload)
            manifest = merge_manifests(embedded, rebuilt) if rebuilt is not None else embedded
            record_evidence_manifest(job_id, tool_name, manifest)
            return manifest
        except Exception:
            pass
    manifest = build_manifest_from_tool_output(tool_name, payload)
    if manifest is not None:
        record_evidence_manifest(job_id, tool_name, manifest)
    return manifest


def record_veil_tool(job_id: str) -> None:
    if not job_id:
        return
    with _lock:
        _veil_counts[job_id] = _veil_counts.get(job_id, 0) + 1


def get_veil_tool_count(job_id: str) -> int:
    if not job_id:
        return 0
    with _lock:
        return _veil_counts.get(job_id, 0)


# Backward-compatible alias used by older middleware.
def record_siem_telemetry_sparse(job_id: str, sparse: bool) -> None:
    if not sparse or not job_id:
        return
    manifest = get_merged_manifest(job_id)
    if manifest is not None:
        return
    record_evidence_manifest(
        job_id,
        "investigate_incident",
        EvidenceManifest(telemetry_level="sparse", max_confidence=0.5),
    )
