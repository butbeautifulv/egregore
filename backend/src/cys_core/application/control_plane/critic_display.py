from __future__ import annotations

import json
from typing import Any

from cys_core.domain.evidence.models import EvidenceManifest


def critic_verdict_visible_to_operator(result: dict[str, Any]) -> bool:
    """Surface critic in UI/SSE only when the gate changed operator-visible state."""
    if result.get("auto_accepted_after_revision_cap"):
        return True
    if not result.get("passed", True):
        return True
    if result.get("revision_enqueued"):
        return True
    return False


def format_critic_operator_message(
    result: dict[str, Any],
    *,
    source_persona: str,
) -> str:
    if result.get("auto_accepted_after_revision_cap"):
        return (
            f"Проверка агента {source_persona}: лимит доработок исчерпан, результат принят автоматически."
        )
    issues = list(result.get("issues_detected") or []) + list(result.get("rejected_claims") or [])
    issues_text = ", ".join(str(item) for item in issues if item) or "требования качества не выполнены"
    if result.get("revision_enqueued"):
        return (
            f"Проверка не пройдена ({source_persona}): {issues_text}. Запрошена доработка агента."
        )
    return f"Проверка не пройдена ({source_persona}): {issues_text}."


def format_soc_revision_manifest_hint(manifest: EvidenceManifest) -> str:
    obs_ids = [obs.obs_id for obs in manifest.observations if obs.obs_id]
    gaps = [gap.model_dump(mode="json") for gap in manifest.data_gaps]
    return (
        "\n\nRequired sparse-SIEM fields from evidence_manifest:\n"
        f"- telemetry_level: {manifest.telemetry_level}\n"
        f"- max_confidence: {manifest.max_confidence}\n"
        f"- data_gaps: {json.dumps(gaps, ensure_ascii=False)}\n"
        f"- valid obs_ids: {json.dumps(obs_ids, ensure_ascii=False)}"
    )
