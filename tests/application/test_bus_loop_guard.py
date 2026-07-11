from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from cys_core.application.bus_fingerprint import envelope_fingerprint
from cys_core.application.bus_guard_config import BusGuardConfig
from cys_core.application.bus_ingress_router import BusIngressRouter
from cys_core.application.engagement_bus_guard import EngagementBusGuard
from cys_core.application.use_cases.enqueue_worker_jobs import EnqueueWorkerJobs
from cys_core.application.use_cases.process_finding_critic import ProcessFindingCritic
from cys_core.application.workers.finding_publisher import WorkerFindingPublisher
from cys_core.domain.engagement.models import Engagement, EngagementStatus
from cys_core.infrastructure.bus_dedup_store import BusDedupStore
from cys_core.infrastructure.job_store.in_memory import InMemoryJobStore
from cys_core.infrastructure.redis_client import ResilientRedisClient


class _OfflineRedisClient(ResilientRedisClient):
    def ensure_connected(self) -> bool:
        return False


class _OfflineEngagementBusGuard(EngagementBusGuard):
    def _ensure_redis(self) -> bool:
        return False

@pytest.mark.unit
def test_is_noop_finding_suppressed() -> None:
    from cys_core.application.workers.noop_finding import is_noop_finding

    assert is_noop_finding({"suppressed": True, "summary": "dup"})
    assert is_noop_finding({"analysis_type": "network_duplicate_suppression"})
    assert not is_noop_finding({"summary": "real alert"})


@pytest.mark.unit
@pytest.mark.asyncio
async def test_suppressed_finding_skips_bus_publish() -> None:
    bus = MagicMock()
    transport = MagicMock()
    transport.publish_delivery = AsyncMock()
    publisher = WorkerFindingPublisher(bus=bus, transport=transport)
    job = MagicMock(persona="network", event_id="e1", correlation_id="eng-abc", tenant_id="default", job_id="j1")
    defn = MagicMock(bus_recipients=["soc"])

    await publisher.publish(
        job=job,
        defn=defn,
        result={"suppressed": True, "summary": "duplicate"},
        sandbox_id="sb",
        investigation_id="eng-abc",
    )

    bus.send_message.assert_not_called()
    transport.publish_delivery.assert_not_called()


@pytest.mark.unit
def test_critic_auto_passes_suppressed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cys_core.application.use_cases.process_finding_critic.record_critic_verdict",
        lambda *args, **kwargs: None,
    )
    critic = ProcessFindingCritic(policy_port=MagicMock())
    result = critic.execute(
        persona="network",
        finding={"suppressed": True, "summary": "noop"},
    )
    assert result["passed"] is True
    assert result.get("auto_passed") is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bus_router_content_dedup_blocks_second_enqueue() -> None:
    from cys_core.infrastructure.bus_dedup_store import BusDedupStore, reset_bus_dedup_store

    reset_bus_dedup_store()
    enqueued: list[str] = []

    async def _enqueue(envelope: dict) -> str:
        enqueued.append(envelope["recipient"])
        return "job-1"

    store = BusDedupStore(redis_url="redis://localhost:6379/0", ttl_seconds=300)
    store._redis = _OfflineRedisClient("redis://localhost:6379/0")
    router = BusIngressRouter(orchestration_enqueue=_enqueue, dedup_store=store)
    engagement_id = "eng-revision-dedup-unique"
    envelope = {
        "recipient": "soc",
        "type": "revision",
        "sender": "critic",
        "payload": {"correlation_id": engagement_id, "data": {"summary": "same-content-dedup-test"}},
    }
    envelope["message_id"] = "msg-1"
    envelope["signature"] = "sig-1"
    await router.route_envelope(envelope)
    envelope["message_id"] = "msg-2"
    envelope["signature"] = "sig-2"
    await router.route_envelope(envelope)
    assert len(enqueued) == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enqueue_from_bus_rejects_closed_engagement() -> None:
    queue = MagicMock()
    queue.aenqueue = AsyncMock()
    job_store = InMemoryJobStore()
    engagement = Engagement(id="eng-deadbeefcafe", tenant_id="default", goal="x")
    engagement.status = EngagementStatus.CLOSED
    store = MagicMock()
    store.get.return_value = engagement

    bus_guard = MagicMock()
    bus_guard.is_tripped.return_value = False
    bus_guard.should_trip.return_value = None
    bus_guard.revision_cap_exceeded.return_value = False

    service = EnqueueWorkerJobs(
        queue=queue, job_store=job_store, engagement_store=store, bus_guard=bus_guard
    )
    job_id = await service.enqueue_from_bus(
        {
            "recipient": "soc",
            "type": "revision",
            "payload": {"correlation_id": "eng-deadbeefcafe", "tenant_id": "default"},
        }
    )
    assert job_id == ""
    queue.aenqueue.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enqueue_from_bus_rate_limit() -> None:
    queue = MagicMock()
    queue.aenqueue = AsyncMock()
    job_store = InMemoryJobStore()
    engagement_id = "eng-cafebabef00d"
    for index in range(20):
        job_store.upsert_pending(
            f"soc-bus-{index}",
            "soc",
            correlation_id=engagement_id,
            tenant_id="default",
        )
        record = job_store.get(f"soc-bus-{index}")
        assert record is not None
        record.status = record.status.__class__.PENDING

    bus_guard = MagicMock()
    bus_guard.is_tripped.return_value = False
    bus_guard.should_trip.return_value = None
    bus_guard.revision_cap_exceeded.return_value = False

    service = EnqueueWorkerJobs(
        queue=queue,
        job_store=job_store,
        engagement_store=MagicMock(),
        bus_guard=bus_guard,
        max_jobs_per_engagement=20,
    )
    job_id = await service.enqueue_from_bus(
        {
            "recipient": "soc",
            "type": "revision",
            "payload": {"correlation_id": engagement_id, "tenant_id": "default"},
        }
    )
    assert job_id == ""
    queue.aenqueue.assert_not_called()


@pytest.mark.unit
def test_envelope_fingerprint_ignores_timestamp() -> None:
    base = {
        "recipient": "soc",
        "type": "revision",
        "sender": "critic",
        "payload": {"correlation_id": "eng-f8c54f425c09", "data": {"summary": "x"}},
    }
    a = dict(base)
    b = dict(base)
    b["timestamp"] = "2026-01-01T00:00:00Z"
    assert envelope_fingerprint(a) == envelope_fingerprint(b)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enqueue_from_bus_rejects_noop_finding() -> None:
    queue = MagicMock()
    queue.aenqueue = AsyncMock()
    service = EnqueueWorkerJobs(queue=queue, job_store=InMemoryJobStore())
    job_id = await service.enqueue_from_bus(
        {
            "recipient": "network",
            "type": "finding",
            "payload": {
                "correlation_id": "eng-f3cb965ffc6a",
                "tenant_id": "default",
                "data": {
                    "response": "duplicate_suppressed",
                    "confidence": 0.15,
                    "summary": "[UNTRUSTED PENDING]",
                },
            },
        }
    )
    assert job_id == ""
    queue.aenqueue.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_critic_no_revision_on_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    from interfaces.control_plane.critic_service import CriticService

    service = CriticService()
    service._enqueue_revision = AsyncMock()
    monkeypatch.setattr(
        "cys_core.application.use_cases.process_finding_critic.record_critic_verdict",
        lambda *args, **kwargs: None,
    )

    await service.handle_message(
        {
            "sender": "network",
            "payload": {
                "correlation_id": "eng-noop-test",
                "tenant_id": "default",
                "data": {"response": "duplicate_suppressed", "confidence": 0.1},
            },
        }
    )
    service._enqueue_revision.assert_not_called()


@pytest.mark.unit
def test_engagement_guard_trips_on_total_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    from cys_core.application.bus_guard_config import BusGuardConfig
    from cys_core.application.engagement_bus_guard import EngagementBusGuard, reset_engagement_bus_guard

    reset_engagement_bus_guard()
    config = BusGuardConfig(
        max_total_jobs_window=3,
        dedup_trip_threshold=5,
        pingpong_trip_threshold=3,
        noop_churn_threshold=10,
        guard_window_seconds=600,
        redis_url="redis://localhost:6379/0",
    )
    guard = EngagementBusGuard(config=config)
    engagement_id = "eng-guard-trip"
    for _ in range(3):
        guard.record_enqueue(engagement_id, "soc", "fp")
    assert guard.should_trip(engagement_id) is not None


@pytest.mark.unit
def test_pingpong_detection(monkeypatch: pytest.MonkeyPatch) -> None:
    from cys_core.application.bus_guard_config import BusGuardConfig
    from cys_core.application.engagement_bus_guard import EngagementBusGuard, reset_engagement_bus_guard

    reset_engagement_bus_guard()
    config = BusGuardConfig(
        max_total_jobs_window=50,
        dedup_trip_threshold=5,
        pingpong_trip_threshold=1,
        noop_churn_threshold=10,
        guard_window_seconds=600,
        redis_url="redis://localhost:6379/0",
    )
    guard = EngagementBusGuard(config=config)
    engagement_id = "eng-pingpong"
    guard.record_enqueue(engagement_id, "soc", "a")
    guard.record_enqueue(engagement_id, "network", "b")
    guard.record_enqueue(engagement_id, "soc", "c")
    assert guard.should_trip(engagement_id) is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_budget_callback_records_api_tokens() -> None:
    from langchain_core.outputs import ChatGeneration, ChatResult
    from langchain_core.messages import AIMessage

    from cys_core.domain.workers.job_budget import JobBudgetTracker
    from cys_core.infrastructure.observability.budget_usage_callback import BudgetUsageCallback

    JobBudgetTracker.configure("sess-budget", max_tokens=100_000, max_cost_usd=10.0, max_tool_calls=50)
    callback = BudgetUsageCallback("sess-budget")
    message = AIMessage(
        content="ok",
        usage_metadata={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
    )
    response = ChatResult(
        generations=[ChatGeneration(message=message)],
        llm_output={"token_usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}},
    )
    await callback.on_chat_model_end(response)
    state = JobBudgetTracker.get("sess-budget")
    assert state is not None
    assert state.tokens_used == 150
    JobBudgetTracker.clear("sess-budget")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_engagement_guard_trips_and_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    from cys_core.application.bus_guard_config import BusGuardConfig
    from cys_core.application import engagement_bus_guard as guard_module
    from cys_core.application.engagement_bus_guard import EngagementBusGuard, TripReason
    from cys_core.application.use_cases.fail_engagement_guardrail import FailEngagementGuardrail
    from cys_core.domain.engagement.models import Engagement
    from cys_core.infrastructure.engagement.memory_store import MemoryEngagementStateStore
    from cys_core.infrastructure.queue import InMemoryJobQueue
    from cys_core.domain.workers.models import WorkerJob

    guard_module.reset_engagement_bus_guard()
    config = BusGuardConfig(
        max_total_jobs_window=2,
        dedup_trip_threshold=5,
        pingpong_trip_threshold=3,
        noop_churn_threshold=10,
        guard_window_seconds=600,
        redis_url="redis://localhost:6379/0",
    )
    guard = _OfflineEngagementBusGuard(config=config)
    guard_module._guard = guard
    engagement_id = "eng-fail-guard"
    store = MemoryEngagementStateStore()
    store.upsert(Engagement(id=engagement_id, tenant_id="default", goal="test"))
    job_store = InMemoryJobStore()
    queue = InMemoryJobQueue()
    queue.enqueue(
        WorkerJob(
            job_id="soc-bus-pending",
            event_id="e1",
            persona="soc",
            correlation_id=engagement_id,
            tenant_id="default",
        )
    )

    guard.record_enqueue(engagement_id, "soc", "fp1")
    guard.record_enqueue(engagement_id, "network", "fp2")
    reason = guard.should_trip(engagement_id)
    assert reason == TripReason.TOTAL_JOBS

    tripped = FailEngagementGuardrail(
        engagement_store=store,
        job_store=job_store,
        queue=queue,
        bus_guard=guard,
    ).execute(tenant_id="default", engagement_id=engagement_id, reason=reason)
    assert tripped is True
    engagement = store.get("default", engagement_id)
    assert engagement is not None
    assert engagement.status == EngagementStatus.FAILED
    assert queue.queue_depth() == 0


@pytest.mark.unit
def test_critic_can_send_revision_to_intel():
    from cys_core.domain.security.agent_bus import AgentTrustLevel, SecureAgentBus

    bus = SecureAgentBus()
    bus.register_agent(
        "critic",
        AgentTrustLevel.PRIVILEGED,
        ["coordinator", "soc", "network", "consultant", "intel", "hunter", "identity"],
    )
    bus.register_agent("intel", AgentTrustLevel.INTERNAL, ["critic", "soc", "hunter"])

    payload = {
        "correlation_id": "eng-deadbeefcafe",
        "tenant_id": "default",
        "feedback": "add IOC context",
    }
    envelope = bus.send_message("critic", "intel", "revision", payload)
    received = bus.receive_message("intel", envelope)

    assert received["correlation_id"] == "eng-deadbeefcafe"
    assert "add IOC context" in received["feedback"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_finding_publisher_filters_off_plan_recipients() -> None:
    bus = MagicMock()
    transport = MagicMock()
    transport.publish_delivery = AsyncMock()
    engagement = Engagement(id="eng-f8c54f425c09", tenant_id="default", goal="x")
    engagement.planner_plan = ["soc", "intel"]
    store = MagicMock()
    store.get.return_value = engagement
    publisher = WorkerFindingPublisher(bus=bus, transport=transport, engagement_store=store)
    job = MagicMock(
        persona="soc",
        event_id="e1",
        correlation_id="eng-f8c54f425c09",
        tenant_id="default",
        job_id="j1",
        payload={},
    )
    defn = MagicMock(bus_recipients=["network", "critic", "coordinator"])

    await publisher.publish(
        job=job,
        defn=defn,
        result={"summary": "real alert"},
        sandbox_id="sb",
        investigation_id="eng-f8c54f425c09",
    )

    recipients = [call.args[1] for call in bus.send_message.call_args_list]
    assert "network" not in recipients
    assert "critic" in recipients
    assert "coordinator" in recipients
    assert transport.publish_delivery.await_count == len(recipients)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enqueue_from_bus_rejects_off_plan_finding() -> None:
    queue = MagicMock()
    queue.aenqueue = AsyncMock()
    engagement = Engagement(id="eng-cafebabef00d", tenant_id="default", goal="x")
    engagement.planner_plan = ["soc", "intel"]
    store = MagicMock()
    store.get.return_value = engagement
    bus_guard = MagicMock()
    bus_guard.is_tripped.return_value = False
    bus_guard.should_trip.return_value = None
    bus_guard.revision_cap_exceeded.return_value = False

    service = EnqueueWorkerJobs(
        queue=queue,
        job_store=InMemoryJobStore(),
        engagement_store=store,
        bus_guard=bus_guard,
    )
    job_id = await service.enqueue_from_bus(
        {
            "recipient": "network",
            "type": "finding",
            "payload": {
                "correlation_id": "eng-cafebabef00d",
                "tenant_id": "default",
                "data": {"summary": "real alert"},
            },
        }
    )
    assert job_id == ""
    queue.aenqueue.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enqueue_from_bus_allows_critic_revision_to_intel_in_plan() -> None:
    queue = MagicMock()
    queue.aenqueue = AsyncMock()
    engagement = Engagement(id="eng-deadbeefcafe", tenant_id="default", goal="x")
    engagement.planner_plan = ["soc", "intel"]
    store = MagicMock()
    store.get.return_value = engagement
    bus_guard = MagicMock()
    bus_guard.is_tripped.return_value = False
    bus_guard.should_trip.return_value = None
    bus_guard.revision_cap_exceeded.return_value = False

    service = EnqueueWorkerJobs(
        queue=queue,
        job_store=InMemoryJobStore(),
        engagement_store=store,
        bus_guard=bus_guard,
    )
    job_id = await service.enqueue_from_bus(
        {
            "recipient": "intel",
            "type": "revision",
            "sender": "critic",
            "payload": {
                "correlation_id": "eng-deadbeefcafe",
                "tenant_id": "default",
                "feedback": "expand IOC context",
            },
        }
    )
    assert job_id != ""
    queue.aenqueue.assert_called_once()


@pytest.mark.unit
def test_maybe_trip_soft_pingpong_when_planner_terminal() -> None:
    from cys_core.application.bus_guard_config import BusGuardConfig
    from cys_core.application.engagement_bus_guard import EngagementBusGuard, TripReason
    from cys_core.application.use_cases.fail_engagement_guardrail import maybe_trip_engagement
    from cys_core.infrastructure.engagement.memory_store import MemoryEngagementStateStore

    config = BusGuardConfig(
        max_total_jobs_window=50,
        dedup_trip_threshold=5,
        pingpong_trip_threshold=1,
        noop_churn_threshold=10,
        guard_window_seconds=600,
        redis_url="redis://localhost:6379/0",
    )
    guard = _OfflineEngagementBusGuard(config=config)
    engagement_id = "eng-a1b2c3d4e5f6"
    store = MemoryEngagementStateStore()
    engagement = Engagement(id=engagement_id, tenant_id="default", goal="x")
    engagement.planner_plan = ["soc", "intel"]
    engagement.completed_personas = ["soc", "intel"]
    store.upsert(engagement)

    guard.record_enqueue(engagement_id, "soc", "a")
    guard.record_enqueue(engagement_id, "network", "b")
    guard.record_enqueue(engagement_id, "soc", "c")

    reason = maybe_trip_engagement(
        tenant_id="default",
        engagement_id=engagement_id,
        engagement_store=store,
        job_store=InMemoryJobStore(),
        bus_guard=guard,
    )
    assert reason == TripReason.PINGPONG
    updated = store.get("default", engagement_id)
    assert updated is not None
    assert updated.status != EngagementStatus.FAILED


@pytest.mark.unit
def test_filter_escalation_recipients_strips_redteam_from_intel() -> None:
    from cys_core.application.bus_planner_gate import filter_escalation_recipients

    recipients = ["critic", "soc", "hunter", "redteam"]
    filtered = filter_escalation_recipients("intel", recipients)
    assert "redteam" not in filtered
    assert "critic" in filtered


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enqueue_from_bus_rejects_second_revision_on_soc() -> None:
    from cys_core.application.bus_guard_config import BusGuardConfig
    from cys_core.application.engagement_bus_guard import EngagementBusGuard

    queue = MagicMock()
    queue.aenqueue = AsyncMock()
    engagement_id = "eng-cafebabef00d"
    config = BusGuardConfig(
        max_total_jobs_window=50,
        dedup_trip_threshold=5,
        pingpong_trip_threshold=3,
        noop_churn_threshold=10,
        guard_window_seconds=600,
        redis_url="redis://localhost:6379/0",
    )
    guard = _OfflineEngagementBusGuard(config=config)
    guard.record_revision(engagement_id, "soc")

    metrics = MagicMock()
    service = EnqueueWorkerJobs(
        queue=queue,
        job_store=InMemoryJobStore(),
        engagement_store=MagicMock(),
        bus_guard=guard,
        metrics=metrics,
        max_revisions_per_persona=1,
    )
    job_id = await service.enqueue_from_bus(
        {
            "recipient": "soc",
            "type": "revision",
            "payload": {"correlation_id": engagement_id, "tenant_id": "default"},
        }
    )
    assert job_id == ""
    queue.aenqueue.assert_not_called()
    metrics.record_bus_revision_rejected.assert_called_once_with("revision_cap")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_critic_auto_accepts_after_revision_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    from cys_core.application.bus_guard_config import BusGuardConfig
    from cys_core.application.engagement_bus_guard import EngagementBusGuard, reset_engagement_bus_guard
    from cys_core.application import engagement_bus_guard as guard_module
    from interfaces.control_plane.critic_service import CriticService

    reset_engagement_bus_guard()
    config = BusGuardConfig(
        max_total_jobs_window=50,
        dedup_trip_threshold=5,
        pingpong_trip_threshold=3,
        noop_churn_threshold=10,
        guard_window_seconds=600,
        redis_url="redis://localhost:6379/0",
    )
    guard = _OfflineEngagementBusGuard(config=config)
    engagement_id = "eng-deadbeefcafe"
    guard.record_revision(engagement_id, "soc")
    guard_module._guard = guard

    settings = MagicMock()
    settings.bus_max_revisions_per_persona = 1
    settings.critic_use_llm_judge = False
    container = MagicMock()
    container.settings = settings
    container.get_profile_policy_port.return_value = MagicMock()
    container.get_application_tracing_port.return_value = MagicMock()
    container.get_schema_registry_port.return_value = MagicMock()
    container.get_agent_runtime.return_value = MagicMock()
    container.get_engagement_egress.return_value = MagicMock()
    monkeypatch.setattr("interfaces.control_plane.critic_service.get_container", lambda: container)
    monkeypatch.setattr(
        "cys_core.application.use_cases.process_finding_critic.record_critic_verdict",
        lambda *args, **kwargs: None,
    )

    service = CriticService()
    service._enqueue_revision = AsyncMock(return_value=True)
    service._critic.execute_async = AsyncMock(return_value={"passed": False, "issues": ["grounding"]})

    result = await service.handle_message(
        {
            "sender": "soc",
            "payload": {
                "correlation_id": engagement_id,
                "tenant_id": "default",
                "data": {"summary": "real alert"},
            },
        }
    )
    service._enqueue_revision.assert_not_called()
    assert result["passed"] is True
    assert result.get("auto_accepted_after_revision_cap") is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_intel_finding_does_not_message_redteam() -> None:
    bus = MagicMock()
    transport = MagicMock()
    transport.publish_delivery = AsyncMock()
    store = MagicMock()
    engagement = Engagement(
        id="eng-intel-esc",
        tenant_id="default",
        goal="test",
        planner_plan=["soc", "intel"],
    )
    store.get.return_value = engagement
    publisher = WorkerFindingPublisher(bus=bus, transport=transport, engagement_store=store)
    job = MagicMock(
        persona="intel",
        event_id="e1",
        correlation_id="eng-intel-esc",
        tenant_id="default",
        job_id="intel-j1",
    )
    defn = MagicMock(bus_recipients=["critic", "soc", "hunter", "redteam"])

    await publisher.publish(
        job=job,
        defn=defn,
        result={"summary": "intel finding", "confidence": 0.5, "iocs": ["1.2.3.4"]},
        sandbox_id="sb",
        investigation_id="eng-intel-esc",
    )

    for call in bus.send_message.call_args_list:
        assert call.args[1] != "redteam"

