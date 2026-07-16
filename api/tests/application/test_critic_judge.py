from __future__ import annotations

import pytest

from cys_core.application.use_cases.process_finding_critic import ProcessFindingCritic
from cys_core.domain.engagement.models import Engagement
from cys_core.domain.evidence.models import EvidenceManifest
from tests.application.port_fakes import fake_policy_port


@pytest.mark.unit
def test_critic_passes_high_trust_score(monkeypatch):
    monkeypatch.setattr(
        "cys_core.application.use_cases.process_finding_critic.record_critic_verdict",
        lambda *a, **k: None,
    )
    critic = ProcessFindingCritic(policy_port=fake_policy_port(), trust_threshold=0.5)
    out = critic.execute(persona="soc", finding={"trust_score": 0.9})
    assert out["passed"] is True
    assert out["trust_score"] == 0.9


@pytest.mark.unit
def test_critic_fails_low_trust_score(monkeypatch):
    monkeypatch.setattr(
        "cys_core.application.use_cases.process_finding_critic.record_critic_verdict",
        lambda *a, **k: None,
    )
    critic = ProcessFindingCritic(policy_port=fake_policy_port(), trust_threshold=0.5)
    out = critic.execute(persona="soc", finding={"trust_score": 0.2})
    assert out["passed"] is False


class _FakeEngagementStore:
    """Stand-in for the durable EngagementStateStore — simulates a worker
    process (different from the critic's) having already persisted the
    evidence manifest, the way finding_publisher.append_engagement_finding
    does in a real deployment."""

    def __init__(self, engagement: Engagement) -> None:
        self._engagement = engagement

    def get(self, tenant_id: str, engagement_id: str) -> Engagement | None:
        if tenant_id == self._engagement.tenant_id and engagement_id == self._engagement.id:
            return self._engagement
        return None


@pytest.mark.unit
def test_critic_reads_evidence_manifest_cross_process_via_engagement_store(monkeypatch):
    """Regression for 5-whys root cause #1 (docs/MICROSERVICES_SPLIT_PHASES_DETAIL.md):
    before this fix, the critic could only see evidence manifests written into
    the process-local tool_execution_tracker module — always empty when the
    critic runs in a different process/container than the worker that
    populated it (every real deployment topology here). The critic must now
    find the manifest through the durable, cross-process EngagementStateStore
    even when the in-process tracker has nothing at all."""
    monkeypatch.setattr(
        "cys_core.application.use_cases.process_finding_critic.record_critic_verdict",
        lambda *a, **k: None,
    )
    manifest = EvidenceManifest(telemetry_level="sparse", max_confidence=0.4)
    engagement = Engagement(
        id="eng-1",
        tenant_id="tenant-1",
        goal="investigate",
        evidence_manifests={"soc": manifest.model_dump(mode="json")},
    )
    critic = ProcessFindingCritic(
        policy_port=fake_policy_port(),
        trust_threshold=0.5,
        engagement_store=_FakeEngagementStore(engagement),
    )
    out = critic.execute(
        persona="soc",
        finding={"trust_score": 0.9},
        investigation_id="eng-1",
        tenant_id="tenant-1",
    )
    # max_confidence=0.4 from the store-backed manifest caps the reported
    # trust_score below the finding's own claimed 0.9 — proof the manifest
    # was actually read, not silently missing (which would leave 0.9 as-is).
    assert out["trust_score"] == 0.4
    assert out["passed"] is False


@pytest.mark.unit
def test_critic_falls_back_to_in_process_tracker_when_no_store_wired(monkeypatch):
    """No engagement_store configured (e.g. a genuinely single-process dev
    deployment, or a test that doesn't care about this path) must behave
    exactly as before this fix — process-local tracker only."""
    monkeypatch.setattr(
        "cys_core.application.use_cases.process_finding_critic.record_critic_verdict",
        lambda *a, **k: None,
    )
    critic = ProcessFindingCritic(policy_port=fake_policy_port(), trust_threshold=0.5)
    out = critic.execute(
        persona="soc",
        finding={"trust_score": 0.9},
        investigation_id="eng-does-not-exist",
        tenant_id="tenant-1",
    )
    assert out["trust_score"] == 0.9
    assert out["passed"] is True
