from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.application.planning.signals import PlannerSignalDetector
from cys_core.domain.catalog.models import AgentCatalogEntry
from cys_core.infrastructure.registry.resource_source_adapter import ResourceSourceAdapter


@pytest.mark.unit
def test_resource_source_filters_by_profile_id() -> None:
    class _Catalog:
        def list_agents(self, *, profile_id: str | None = None, enabled_only: bool = True):
            del enabled_only
            rows = [
                AgentCatalogEntry(name="soc", role="worker", profile_id="cybersec-soc"),
                AgentCatalogEntry(name="consultant", role="worker", profile_id="cybersec-soc"),
                AgentCatalogEntry(name="gaia-helper", role="worker", profile_id="gaia"),
            ]
            return [row for row in rows if row.profile_id == (profile_id or "cybersec-soc")]

    registry = MagicMock()
    registry.by_workers.return_value = [MagicMock(name="soc"), MagicMock(name="consultant")]
    adapter = ResourceSourceAdapter(registry, agent_catalog=_Catalog())

    personas = adapter.list_worker_personas(profile_id="cybersec-soc")

    assert personas == ["soc", "consultant"]


@pytest.mark.unit
def test_planner_signal_detector_incident_and_advisory() -> None:
    incident = PlannerSignalDetector(payload={"incident_id": "INC-42"}, intake={})
    assert incident.incident_id_present() is True
    assert incident.advisory() is False

    advisory = PlannerSignalDetector(payload={"goal": "Explain DevSecOps best practices"}, intake={})
    assert advisory.advisory() is True
    assert advisory.incident_id_present() is False
