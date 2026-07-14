from __future__ import annotations

import threading
from typing import Any

from bootstrap.settings import get_settings
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
    if len(text) > get_settings().tool_output_preview_max:
        text = text[: get_settings().tool_output_preview_max] + "…"
    with _lock:
        entries = _outputs.setdefault(job_id, [])
        entries.append((tool_name, text))
        max_stored = get_settings().tool_stored_outputs_max
        if len(entries) > max_stored:
            del entries[: len(entries) - max_stored]


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


# NOTE(evidence-grounding-consolidation, 2026-07-14): `get_merged_manifest(job_id)` and
# `get_persona_manifests(investigation_id).get(persona)` are NOT interchangeable, and the
# grounding logic that consumes them (run_worker_job._apply_soc_sparse_coerce vs.
# process_finding_critic._structural_issues/_resolve_trust_score) was investigated for
# consolidation onto a single lookup. Verified findings, so the next person doesn't have to
# re-derive them:
#
# 1. Relationship between the two stores (this module):
#    - `_manifests` (job_id -> list[EvidenceManifest]) is written live, during a job's tool
#      calls, by `ingest_tool_output_manifest` (via cys_core/middleware/tool_coercion_middleware.py)
#      and by `seed_job_from_persona_manifest`. `get_merged_manifest(job_id)` merges that list.
#      This is what run_worker_job.py reads *during* a job (mid-retry-loop and in
#      `_handle_invalid_finding`), before the finding has been accepted/published.
#    - `_persona_manifests` (investigation_id -> {persona: EvidenceManifest}) is a *derived*
#      snapshot: `WorkerFindingPublisher.append_engagement_finding` (finding_publisher.py)
#      calls `get_merged_manifest(job.job_id)` for the job whose finding just passed
#      `finding_meets_minimum`, then writes that exact manifest into `_persona_manifests` via
#      `record_persona_manifest(investigation_id, persona, manifest)` (which further merges it
#      with any prior manifest recorded for that persona in the same investigation). So within
#      a single process, persona-manifest is a (possibly broader, multi-job) superset of the
#      job's merged manifest as of the moment that job's finding was published — not
#      independently-sourced data, but not a live mirror of the *current* job either.
#
# 2. Process locality (the actual blocker to unifying the lookups): both `_manifests` and
#    `_persona_manifests` are plain module-level dicts guarded by an in-process `threading.Lock`
#    — there is no Redis/Postgres/Kafka backing. The worker (`egregore worker --daemon`, its own
#    container — see docker-compose.dev.yml `worker` service) and the critic (`egregore critic
#    --daemon`, or instantiated in-process inside the `api` server when CONTROL_MODE=inprocess,
#    the default — see interfaces/api/app.py, interfaces/control_plane/critic_daemon.py) run as
#    SEPARATE OS processes in every real deployment topology in this repo. The worker's writes to
#    `_manifests`/`_persona_manifests` therefore never reach the critic's copy of this module —
#    `process_finding_critic._structural_issues`/`_resolve_trust_score` see an empty dict for
#    `get_persona_manifests(investigation_id)` in that process almost always, meaning the SOC
#    grounding gate the critic is supposed to run is effectively a silent no-op in a distributed
#    deployment. This is NOT caught by tests because pytest runs producer and consumer in the
#    same interpreter, so the module-level dicts happen to be shared there.
#    -> Swapping the critic to call `get_merged_manifest(job_id)` instead would NOT fix this: that
#       dict is populated only in the worker process and is equally invisible to the critic.
#    -> Separately, `interfaces/control_plane/control_message_handler.py::extract_context`
#       currently synthesizes `job_id` as `f"{sender}:{investigation_id}"` rather than reading the
#       real `job.job_id` that `finding_publisher.publish()` already puts in the bus payload
#       (`finding_payload["job_id"]`), so "just thread job_id through" is not a drop-in fix either.
#    -> The one piece of this data that IS cross-process-safe already exists:
#       `finding_publisher.append_engagement_finding` also persists
#       `manifest.model_dump(mode="json")` into `engagement.evidence_manifests[persona]` via
#       `EngagementStateStore` (Postgres-backed in prod — see
#       cys_core/infrastructure/engagement/postgres_store.py). `process_finding_critic.py` does
#       not currently read from that store at all.
#
# Given the above, consolidating the two call sites onto either existing lookup function would be
# cosmetic at best and could mask the real bug (critic grounding gate not seeing worker evidence
# cross-process) behind a false sense of "now they agree." Left unchanged pending a deliberate
# fix: give `ProcessFindingCritic` access to `EngagementStateStore` and read
# `engagement.evidence_manifests[persona]` (re-hydrated via `EvidenceManifest.model_validate`),
# or carry the merged manifest directly on the bus finding payload. See also the mirrored note in
# cys_core/application/use_cases/process_finding_critic.py.
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
        return _siem_drilldown_counts.get(job_id, 0) >= get_settings().tool_siem_drilldown_max


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
