from __future__ import annotations

from typing import Any

import structlog

from cys_core.application.ports.engagement_store import EngagementStateStore
from cys_core.application.ports.schema_registry import SchemaRegistryPort
from cys_core.application.ports.tracing_ports import ApplicationTracingPort
from cys_core.application.runtime_config import get_critic_default_confidence, get_critic_trust_threshold
from cys_core.application.workers.evidence_gate import soc_evidence_gaps
from cys_core.application.workers.noop_finding import is_noop_finding
from cys_core.application.workers.tool_execution_tracker import resolve_persona_manifest
from cys_core.domain.evidence.coercion import coerce_sparse_soc_finding

logger = structlog.get_logger(__name__)


def record_critic_verdict(
    *,
    persona: str,
    investigation_id: str,
    tenant_id: str,
    passed: bool,
    trust_score: float,
    issues: list[str] | None = None,
) -> None:
    logger.info(
        "critic_verdict",
        persona=persona,
        investigation_id=investigation_id,
        tenant_id=tenant_id,
        passed=passed,
        trust_score=trust_score,
        issues_detected=issues or [],
    )


class ProcessFindingCritic:
    """Validate specialist findings before downstream propagation.

    In-app LLM judge (runtime/use_llm_judge) was removed — see ADR-007 and
    ADR-006: use Langfuse platform eval for LLM-quality monitoring instead.
    This class only runs the local trust/evidence-gap heuristic gate.
    """

    def __init__(
        self,
        *,
        policy_port: Any,
        application_tracing: ApplicationTracingPort | None = None,
        schema_registry: SchemaRegistryPort | None = None,
        trust_threshold: float | None = None,
        engagement_store: EngagementStateStore | None = None,
    ) -> None:
        self._policy_port = policy_port
        self._application_tracing = application_tracing
        self._schema_registry = schema_registry
        self._engagement_store = engagement_store
        self.trust_threshold = (
            trust_threshold
            if trust_threshold is not None
            else get_critic_trust_threshold()
        )

    # NOTE(evidence-grounding-consolidation, 2026-07-14, updated by 5-whys root cause #1 fix):
    # this used to read `get_persona_manifests` (investigation-keyed, process-local) directly,
    # which is typically empty here in a real (multi-container) deployment because the worker
    # that populates it runs in a separate process — see the note above `record_evidence_manifest`
    # in cys_core/application/workers/tool_execution_tracker.py. Now goes through
    # `resolve_persona_manifest()`, which reads the durable, cross-process EngagementStateStore
    # first and only falls back to the process-local tracker when no store is wired.
    def _resolve_trust_score(
        self,
        finding: dict[str, Any],
        persona: str,
        investigation_id: str | None,
        tenant_id: str | None = None,
    ) -> float:
        default_confidence = get_critic_default_confidence()
        try:
            confidence = float(
                finding.get("confidence", finding.get("trust_score", default_confidence))
            )
        except (TypeError, ValueError):
            confidence = default_confidence
        if persona == "soc" and investigation_id:
            manifest = resolve_persona_manifest(
                self._engagement_store,
                tenant_id=tenant_id,
                investigation_id=investigation_id,
                persona=persona,
            )
            if manifest is not None:
                return min(confidence, manifest.max_confidence)
        return confidence

    def _structural_issues(
        self,
        persona: str,
        finding: dict[str, Any],
        investigation_id: str | None,
        tenant_id: str | None = None,
    ) -> list[str]:
        if persona != "soc" or not investigation_id:
            return []
        manifest = resolve_persona_manifest(
            self._engagement_store,
            tenant_id=tenant_id,
            investigation_id=investigation_id,
            persona=persona,
        )
        if manifest is None:
            return []
        normalized = dict(finding)
        coerce_sparse_soc_finding(normalized, manifest)
        return soc_evidence_gaps(normalized, manifest)

    def execute(
        self,
        *,
        persona: str,
        finding: dict[str, Any],
        investigation_id: str | None = None,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        if is_noop_finding(finding):
            return {"passed": True, "auto_passed": True, "trust_score": 1.0, "issues_detected": []}

        issues = self._structural_issues(persona, finding, investigation_id, tenant_id)
        trust_score = self._resolve_trust_score(finding, persona, investigation_id, tenant_id)
        passed = trust_score >= self.trust_threshold and not issues
        result = {
            "passed": passed,
            "trust_score": trust_score,
            "issues_detected": issues,
            "validated_claims": [] if issues else ["finding_structure_ok"],
            "rejected_claims": issues,
            "recommended_disposition": "accept" if passed else "revise",
        }
        if investigation_id:
            record_critic_verdict(
                persona=persona,
                investigation_id=investigation_id,
                tenant_id=tenant_id or "default",
                passed=passed,
                trust_score=trust_score,
                issues=issues,
            )
        return result

    async def execute_async(
        self,
        *,
        persona: str,
        finding: dict[str, Any],
        investigation_id: str | None = None,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        return self.execute(
            persona=persona,
            finding=finding,
            investigation_id=investigation_id,
            tenant_id=tenant_id,
        )
