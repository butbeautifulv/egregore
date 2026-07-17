from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from bootstrap.settings import settings
from cys_core.infrastructure.kafka_topics import AUDIT_HITL_APPROVALS_TOPIC


class HitlApprovalRecord(BaseModel):
    approval_id: str
    actor: str
    tool: str
    persona: str
    job_id: str
    sandbox_id: str = ""
    target_resource: str = ""
    params_hash: str
    decision: str
    expiry: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


_approval_records: list[dict[str, Any]] = []


def get_approval_records() -> list[dict[str, Any]]:
    return list(_approval_records)


def clear_approval_records() -> None:
    _approval_records.clear()


def params_hash(args: dict[str, Any]) -> str:
    normalized = json.dumps(args, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(normalized.encode()).hexdigest()


def create_approval_id() -> str:
    return f"appr-{uuid.uuid4().hex[:12]}"


async def publish_hitl_approval(record: HitlApprovalRecord) -> bool:
    if not settings.use_kafka:
        return True
    try:
        from aiokafka import AIOKafkaProducer

        producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
        await producer.start()
        try:
            await producer.send_and_wait(
                AUDIT_HITL_APPROVALS_TOPIC,
                json.dumps(record.model_dump(), ensure_ascii=False).encode(),
            )
            return True
        finally:
            await producer.stop()
    except Exception:
        return False


def publish_hitl_approval_sync(record: HitlApprovalRecord) -> bool:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(publish_hitl_approval(record))
    return True


def record_hitl_approval(
    *,
    actor: str,
    tool: str,
    persona: str,
    job_id: str,
    decision: str,
    tool_args: dict[str, Any],
    sandbox_id: str = "",
    approval_id: str | None = None,
) -> HitlApprovalRecord:
    record = HitlApprovalRecord(
        approval_id=approval_id or create_approval_id(),
        actor=actor,
        tool=tool,
        persona=persona,
        job_id=job_id,
        sandbox_id=sandbox_id,
        target_resource=tool_args.get("target", tool_args.get("command", "")),
        params_hash=params_hash(tool_args),
        decision=decision,
    )
    payload = record.model_dump()
    _approval_records.append(payload)
    if settings.use_kafka:
        publish_hitl_approval_sync(record)
    return record
