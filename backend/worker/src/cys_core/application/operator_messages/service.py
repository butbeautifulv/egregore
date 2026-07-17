from __future__ import annotations

import json
from typing import Any

from cys_core.domain.follow_up.models import initial_follow_up_id
from cys_core.domain.memory.services import MemoryReadService, MemoryWriteService

__all__ = [
    "initial_follow_up_id",
    "is_follow_up_turn_id",
    "is_initial_turn_id",
    "maybe_compact_context",
    "persist_operator_turn_to_memory",
]


def is_initial_turn_id(follow_up_id: str) -> bool:
    return str(follow_up_id).startswith("wo-")


def is_follow_up_turn_id(follow_up_id: str) -> bool:
    return str(follow_up_id).startswith("fu-")


def persist_operator_turn_to_memory(
    memory_writer: MemoryWriteService,
    *,
    tenant_id: str,
    engagement_id: str,
    message: str,
    follow_up_id: str,
    work_kind: str = "",
    mode: str = "auto",
    metrics: Any | None = None,
    memory_reader: MemoryReadService | None = None,
    engagement_store: Any | None = None,
) -> str:
    entry = memory_writer.append_conversation_turn(
        tenant_id=tenant_id,
        investigation_id=engagement_id,
        role="operator",
        text=message.strip(),
        follow_up_id=follow_up_id,
        source_agent="operator",
        work_kind=work_kind,
        mode=mode,
        status="completed",
    )
    if entry is None:
        raise ValueError("conversation_turn_rejected")
    if metrics is not None:
        record = getattr(metrics, "record_memory_write", None)
        if callable(record):
            record(tenant_id, "conversation")
    maybe_compact_context(
        memory_reader=memory_reader,
        engagement_store=engagement_store,
        tenant_id=tenant_id,
        engagement_id=engagement_id,
    )
    return follow_up_id


def maybe_compact_context(
    *,
    memory_reader: MemoryReadService | None,
    engagement_store: Any | None,
    tenant_id: str,
    engagement_id: str,
) -> None:
    if memory_reader is None or engagement_store is None:
        return
    turns = memory_reader.query_conversation_turns(tenant_id, engagement_id, limit=200)
    if len(turns) <= 10:
        return
    engagement = engagement_store.get(tenant_id, engagement_id)
    if engagement is None:
        return
    older = turns[:-10]
    lines: list[str] = []
    for entry in older:
        try:
            data = json.loads(entry.content)
            role = str(data.get("role", "unknown"))
            text = str(data.get("text", ""))[:240]
            lines.append(f"{role}: {text}")
        except json.JSONDecodeError:
            lines.append(entry.content[:240])
    if not lines:
        return
    checkpoint = "\n".join(lines)
    prior = (engagement.context_summary or "").strip()
    engagement.context_summary = f"{prior}\n{checkpoint}".strip()[-4000:]
    engagement_store.upsert(engagement)
