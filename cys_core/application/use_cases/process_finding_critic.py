from __future__ import annotations

import structlog
from typing import Any

from cys_core.application.ports.schema_registry import SchemaRegistryPort
from cys_core.application.ports.tracing_ports import ApplicationTracingPort
from cys_core.application.workers.evidence_gate import soc_evidence_gaps
from cys_core.application.workers.noop_finding import is_noop_finding
from cys_core.application.workers.tool_execution_tracker import get_persona_manifests
from cys_core.domain.evidence.coercion import coerce_sparse_soc_finding
from cys_core.domain.evidence.models import EvidenceManifest

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
        trust_threshold: float = 0.5,
    ) -> None:
        self._policy_port = policy_port
        self._application_tracing = application_tracing
        self._schema_registry = schema_registry
        self.trust_threshold = trust_threshold

    # NOTE(evidence-grounding-consolidation, 2026-07-14): this reads `get_persona_manifests`
    # (investigation-keyed), while run_worker_job._apply_soc_sparse_coerce reads
    # `get_merged_manifest` (job-keyed) from the same tool_execution_tracker module for the
    # *same finding*. Investigated whether to unify these onto one lookup; deliberately left
    # as-is. Full rationale — including why both lookups are process-local and typically empty
    # in the critic's process in a real (multi-container) deployment, and why the fix is not a
    # simple key swap — is documented above `record_evidence_manifest` in
    # cys_core/application/workers/tool_execution_tracker.py. Do not "fix" this without reading
    # that note first.
    def _resolve_trust_score(self, finding: dict[str, Any], persona: str, investigation_id: str | None) -> float:
        try:
            confidence = float(finding.get("confidence", finding.get("trust_score", 0.5)))
        except (TypeError, ValueError):
            confidence = 0.5
        if persona == "soc" and investigation_id:
            manifests = get_persona_manifests(investigation_id)
            manifest = manifests.get(persona)
            if manifest is not None:
                return min(confidence, manifest.max_confidence)
        return confidence

    def _structural_issues(self, persona: str, finding: dict[str, Any], investigation_id: str | None) -> list[str]:
        if persona != "soc" or not investigation_id:
            return []
        manifests = get_persona_manifests(investigation_id)
        manifest = manifests.get(persona)
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

        issues = self._structural_issues(persona, finding, investigation_id)
        trust_score = self._resolve_trust_score(finding, persona, investigation_id)
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
