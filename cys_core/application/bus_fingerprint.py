from __future__ import annotations

import hashlib
import json
from typing import Any

from cys_core.application.workers.noop_signals import revision_semantic_dedup_key, semantic_dedup_key


def _canonical_payload(payload: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(payload)
    for key in ("timestamp", "signature", "message_id", "_trace_carrier"):
        cleaned.pop(key, None)
    data = cleaned.get("data")
    if isinstance(data, dict):
        nested = dict(data)
        nested.pop("timestamp", None)
        nested.pop("job_id", None)
        cleaned["data"] = nested
    return cleaned


def envelope_fingerprint(envelope: dict[str, Any]) -> str:
    """Stable hash for ingress dedup (ignores per-message timestamps/signatures)."""
    payload = envelope.get("payload", {})
    if not isinstance(payload, dict):
        payload = {}

    msg_type = str(envelope.get("type", "")).lower()
    if msg_type == "revision":
        engagement_id = str(payload.get("correlation_id", payload.get("event_id", "")))
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        event_id = str(data.get("event_id", engagement_id)) if isinstance(data, dict) else engagement_id
        revision_key = revision_semantic_dedup_key(
            engagement_id=engagement_id,
            recipient=str(envelope.get("recipient", "")),
            event_id=event_id,
        )
        if revision_key is not None:
            return hashlib.sha256(revision_key.encode("utf-8")).hexdigest()

    semantic = semantic_dedup_key(payload)
    if semantic is not None:
        return hashlib.sha256(semantic.encode("utf-8")).hexdigest()

    body = {
        "recipient": str(envelope.get("recipient", "")),
        "type": str(envelope.get("type", "")),
        "sender": str(envelope.get("sender", "")),
        "payload": _canonical_payload(payload),
    }
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
