from __future__ import annotations

import json
from typing import Any, Protocol

from cys_core.application.persona_quality_hooks import record_critic_verdict
from cys_core.application.ports.profile_policy import ProfilePolicyPort
from cys_core.application.ports.schema_registry import SchemaRegistryPort
from cys_core.application.ports.tracing_ports import ApplicationTracingPort, NOOP_APPLICATION_TRACING
from cys_core.application.workers.noop_finding import is_noop_finding


class CriticRuntimePort(Protocol):
    async def arun(
        self,
        name: str,
        user_input: str,
        *,
        session_id: str | None = None,
        tenant_id: str | None = None,
        investigation_id: str | None = None,
    ) -> dict[str, Any]: ...


class ProcessFindingCritic:
    """Finding critic — optional LLM CriticResult or trust-score gate."""

    def __init__(
        self,
        *,
        policy_port: ProfilePolicyPort,
        trust_threshold: float | None = None,
        application_tracing: ApplicationTracingPort | None = None,
        runtime: CriticRuntimePort | None = None,
        use_llm_judge: bool = False,
        schema_registry: SchemaRegistryPort | None = None,
    ) -> None:
        self.policy_port = policy_port
        self.trust_threshold = trust_threshold
        self._tracing = application_tracing or NOOP_APPLICATION_TRACING
        self._runtime = runtime
        self._use_llm_judge = use_llm_judge
        self._schema_registry = schema_registry

    def _auto_pass_suppressed(self, finding: dict[str, Any]) -> dict[str, Any] | None:
        if not isinstance(finding, dict):
            return None
        if is_noop_finding(finding):
            return {
                "passed": True,
                "trust_score": 1.0,
                "auto_passed": True,
                "reason": "suppressed_noop_finding",
            }
        if finding.get("suppressed") is True and str(finding.get("severity", "")).lower() == "informational":
            return {
                "passed": True,
                "trust_score": 1.0,
                "auto_passed": True,
                "reason": "informational_suppressed",
            }
        return None

    def execute(self, *, persona: str, finding: dict[str, Any], profile_id: str = "cybersec-soc") -> dict[str, Any]:
        auto = self._auto_pass_suppressed(finding)
        if auto is not None:
            record_critic_verdict(persona, passed=True, trust_score=auto["trust_score"])
            return auto
        investigation_id = str(finding.get("correlation_id", finding.get("investigation_id", "")))
        with self._tracing.span(
            "control.critic.process",
            persona=persona,
            engagement_id=investigation_id,
            tenant_id=str(finding.get("tenant_id", "default")),
        ):
            return self._trust_gate_verdict(persona=persona, finding=finding, profile_id=profile_id)

    async def execute_async(
        self,
        *,
        persona: str,
        finding: dict[str, Any],
        investigation_id: str = "",
        tenant_id: str = "default",
        profile_id: str = "cybersec-soc",
    ) -> dict[str, Any]:
        auto = self._auto_pass_suppressed(finding)
        if auto is not None:
            record_critic_verdict(persona, passed=True, trust_score=auto["trust_score"])
            return auto
        with self._tracing.span(
            "control.critic.process",
            persona=persona,
            engagement_id=investigation_id,
            tenant_id=tenant_id,
        ):
            if self._use_llm_judge and self._runtime is not None and investigation_id:
                try:
                    return await self._llm_verdict(
                        persona=persona,
                        finding=finding,
                        investigation_id=investigation_id,
                        tenant_id=tenant_id,
                        profile_id=profile_id,
                    )
                except Exception:
                    pass
            return self._trust_gate_verdict(persona=persona, finding=finding, profile_id=profile_id)

    async def _llm_verdict(
        self,
        *,
        persona: str,
        finding: dict[str, Any],
        investigation_id: str,
        tenant_id: str,
        profile_id: str,
    ) -> dict[str, Any]:
        threshold = self._resolve_threshold(profile_id)
        prompt = json.dumps(
            {
                "persona": persona,
                "finding": finding,
                "investigation_id": investigation_id,
                "instructions": (
                    "Evaluate the worker finding. Return structured CriticResult: trust_score, "
                    "issues_detected, validated_claims, rejected_claims, reasoning_notes, "
                    "recommended_disposition."
                ),
            },
            ensure_ascii=False,
        )
        raw = await self._runtime.arun(  # type: ignore[union-attr]
            "critic",
            prompt,
            session_id=f"critic:{investigation_id}",
            tenant_id=tenant_id,
            investigation_id=investigation_id,
        )
        if not isinstance(raw, dict):
            raise ValueError("critic_llm_invalid_response")
        if self._schema_registry is None:
            return None
        schema = self._schema_registry.get("CriticResult")
        if schema is not None:
            parsed = schema.model_validate(raw).model_dump()
        else:
            parsed = dict(raw)
        trust_score = float(parsed.get("trust_score", 0.0))
        issues = parsed.get("issues_detected") or []
        disposition = str(parsed.get("recommended_disposition", "")).lower()
        passed = (
            "error" not in finding
            and trust_score >= threshold
            and not issues
            and disposition not in {"reject", "rejected", "fail", "failed"}
        )
        record_critic_verdict(persona, passed=passed, trust_score=trust_score)
        return {
            "passed": passed,
            "trust_score": trust_score,
            "threshold": threshold,
            **parsed,
        }

    def _resolve_threshold(self, profile_id: str) -> float:
        if self.trust_threshold is not None:
            return self.trust_threshold
        return self.policy_port.get_trust_floor(profile_id)

    def _trust_gate_verdict(self, *, persona: str, finding: dict[str, Any], profile_id: str) -> dict[str, Any]:
        threshold = self._resolve_threshold(profile_id)
        trust_score = float(finding.get("trust_score", 0.75))
        passed = "error" not in finding and trust_score >= threshold
        record_critic_verdict(persona, passed=passed, trust_score=trust_score)
        return {"passed": passed, "trust_score": trust_score, "threshold": threshold}
