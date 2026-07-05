from __future__ import annotations

import pytest

from cys_core.application.use_cases.update_persona_quality import UpdatePersonaQuality
from cys_core.domain.catalog.models import AgentCatalogEntry
from cys_core.domain.catalog.quality_events import PersonaQualityEvent, PersonaQualityEventKind
from tests.application.port_fakes import fake_policy_port
from tests.conftest import FakePolicyPort, catalog_with_soc_profile


@pytest.mark.unit
def test_update_persona_quality_ema():
    catalog = catalog_with_soc_profile(
        agents=[AgentCatalogEntry(name="soc", profile_id="cybersec-soc")],
    )
    from cys_core.domain.catalog.models import ProfilePolicyPayload

    policy = ProfilePolicyPayload()
    updater = UpdatePersonaQuality(catalog, policy_port=FakePolicyPort(policy))
    updater.apply(
        PersonaQualityEvent(
            persona="soc",
            kind=PersonaQualityEventKind.JOB_COMPLETED,
            trust_signal=0.9,
        )
    )
    entry = catalog.get_agent("soc")
    assert entry is not None
    assert entry.quality.sample_size == 1
    assert entry.quality.empirical_trust > 0.75
