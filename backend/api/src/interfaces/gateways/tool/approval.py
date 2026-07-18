from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from pydantic import BaseModel, Field

from bootstrap.settings import settings
from cys_core.infrastructure.kafka_topics import AUDIT_HITL_APPROVALS_TOPIC

logger = structlog.get_logger(__name__)


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

        from cys_core.infrastructure.kafka_retry import start_with_retry

        async def _build() -> AIOKafkaProducer:
            built = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
            await built.start()
            return built

        producer = await start_with_retry(_build, source="hitl_approval_publish")
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


def _log_hitl_publish_outcome(task: "asyncio.Task[bool]") -> None:
    if task.cancelled():
        return
    if not task.result():
        logger.warning("hitl_approval_kafka_publish_failed")


def publish_hitl_approval_sync(record: HitlApprovalRecord) -> bool:
    """Fire-and-forget the Kafka publish when already inside a running loop.

    A bare `asyncio.run(...)` can't be called from inside a running loop, and the
    original code short-circuited to `return True` in that case without ever
    publishing — silently dropping the HITL approval audit record on every call
    made from async code (the only real production caller, ResumeHitlJob.execute,
    always runs inside a loop). Scheduling a task actually delivers it; the
    done-callback surfaces publish failures instead of hiding them."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(publish_hitl_approval(record))
    task = loop.create_task(publish_hitl_approval(record))
    task.add_done_callback(_log_hitl_publish_outcome)
    return True


async def record_hitl_approval_blocking(
    *,
    actor: str,
    tool: str,
    persona: str,
    job_id: str,
    decision: str,
    tool_args: dict[str, Any],
    sandbox_id: str = "",
    approval_id: str | None = None,
) -> tuple[HitlApprovalRecord, bool]:
    """Like record_hitl_approval, but awaits the real Kafka publish outcome instead of
    firing-and-forgetting it (docs/MICROSERVICES_SPLIT_PLAN.md §10.3/§41). Used for the
    approve/edit HITL decision path: a high-risk action is about to execute off the back
    of this audit record, so a publish failure needs to be observable to the caller rather
    than degrading to a background warning log the caller never sees."""
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
    _approval_records.append(record.model_dump())
    published = await publish_hitl_approval(record)
    if not published:
        logger.warning(
            "hitl_approval_kafka_publish_failed",
            job_id=job_id,
            approval_id=record.approval_id,
            blocking=True,
        )
    return record, published


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
