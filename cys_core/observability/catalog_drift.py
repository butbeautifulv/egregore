from __future__ import annotations

import structlog

from cys_core.observability.metrics import metrics

logger = structlog.get_logger(__name__)


def report_catalog_drift(*, agent_name: str, field: str, expected: set[str], actual: set[str]) -> None:
    missing = expected - actual
    drift = bool(missing)
    metrics.set_catalog_drift(agent_name, field, drift=drift)
    if drift:
        logger.error(
            "catalog_drift_detected",
            agent=agent_name,
            field=field,
            missing=sorted(missing),
            actual=sorted(actual),
        )


def verify_critic_intel_recipient(catalog) -> bool:
    try:
        agent = catalog.get_agent("critic")
    except Exception:
        report_catalog_drift(agent_name="critic", field="bus_recipients", expected={"intel"}, actual=set())
        return False
    recipients = set(agent.bus_recipients or [])
    report_catalog_drift(agent_name="critic", field="bus_recipients", expected={"intel"}, actual=recipients)
    return "intel" in recipients
