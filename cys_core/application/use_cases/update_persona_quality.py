from __future__ import annotations

from datetime import datetime, timezone

from cys_core.application.catalog_mutation_service import CatalogMutationService
from cys_core.application.ports.catalog import AgentCatalogPort
from cys_core.application.ports.metrics import MetricsPort
from cys_core.application.ports.profile_policy import ProfilePolicyPort
from cys_core.domain.catalog.quality_events import PersonaQualityEvent, PersonaQualityEventKind
from cys_core.domain.catalog.trust import declared_trust_score


def _ema(previous: float, sample: float, *, alpha: float) -> float:
    if previous <= 0:
        return sample
    return (1 - alpha) * previous + alpha * sample


class UpdatePersonaQuality:
    def __init__(
        self,
        catalog: AgentCatalogPort,
        *,
        policy_port: ProfilePolicyPort,
        metrics_port: MetricsPort | None = None,
        mutation: CatalogMutationService | None = None,
    ) -> None:
        self._catalog = catalog
        self._policy_port = policy_port
        self._metrics = metrics_port
        self._mutation = mutation

    def apply(self, event: PersonaQualityEvent) -> None:
        entry = self._catalog.get_agent(event.persona)
        if entry is None:
            return
        alpha = self._policy_port.get_policy(event.profile_id).quality_signals.ema_alpha
        quality = entry.quality
        quality.sample_size += 1
        quality.last_evaluated_at = datetime.now(timezone.utc)

        if event.kind in (PersonaQualityEventKind.JOB_COMPLETED, PersonaQualityEventKind.JOB_FAILED):
            success = event.kind == PersonaQualityEventKind.JOB_COMPLETED
            quality.job_success_rate = _ema(quality.job_success_rate, 1.0 if success else 0.0, alpha=alpha)
            quality.avg_cost_usd = _ema(quality.avg_cost_usd, event.cost_usd, alpha=alpha)
            quality.empirical_trust = _ema(quality.empirical_trust, event.trust_signal, alpha=alpha)
        elif event.kind in (PersonaQualityEventKind.CRITIC_PASS, PersonaQualityEventKind.CRITIC_FAIL):
            passed = event.kind == PersonaQualityEventKind.CRITIC_PASS
            quality.critic_pass_rate = _ema(quality.critic_pass_rate, 1.0 if passed else 0.0, alpha=alpha)
            quality.empirical_trust = _ema(quality.empirical_trust, event.trust_signal, alpha=alpha)
        elif event.kind in (PersonaQualityEventKind.TRACE_CRITIC_PASS, PersonaQualityEventKind.TRACE_CRITIC_FAIL):
            passed = event.kind == PersonaQualityEventKind.TRACE_CRITIC_PASS
            quality.trace_critic_pass_rate = _ema(quality.trace_critic_pass_rate, 1.0 if passed else 0.0, alpha=alpha)
            quality.empirical_trust = _ema(quality.empirical_trust, event.trust_signal, alpha=alpha)
        elif event.kind == PersonaQualityEventKind.HITL_PAUSE:
            quality.hitl_rate = _ema(quality.hitl_rate, 1.0, alpha=alpha)
            quality.empirical_trust = _ema(quality.empirical_trust, event.trust_signal, alpha=alpha)
        elif event.kind == PersonaQualityEventKind.BUS_FAILURE:
            quality.empirical_trust = _ema(quality.empirical_trust, event.trust_signal, alpha=alpha)

        entry.quality = quality
        if self._mutation is not None:
            self._mutation.upsert_agent(entry, actor="quality")
        else:
            self._catalog.upsert_agent(entry)
        if self._metrics is not None:
            self._metrics.set_agent_trust_score(entry.name, declared_trust_score(entry))
