from __future__ import annotations

import pytest

from cys_core.domain.security.classification import DataClassification, SecureContextBuilder


@pytest.mark.unit
def test_classify_text_restricted_and_confidential():
    builder = SecureContextBuilder(persona="soc")
    assert builder.classify_text("employee ssn 123") == DataClassification.RESTRICTED
    assert builder.classify_text("api_key leaked") == DataClassification.CONFIDENTIAL
    assert builder.classify_text("routine alert") == DataClassification.INTERNAL


@pytest.mark.unit
def test_persona_clearance_and_access():
    soc = SecureContextBuilder(persona="soc")
    critic = SecureContextBuilder(persona="critic")
    compliance = SecureContextBuilder(persona="compliance")

    assert soc.can_access(DataClassification.CONFIDENTIAL)
    assert not critic.can_access(DataClassification.CONFIDENTIAL)
    assert compliance.include_in_context(DataClassification.RESTRICTED)
    assert not soc.include_in_context(DataClassification.RESTRICTED)


@pytest.mark.unit
def test_redact_and_log_rules():
    builder = SecureContextBuilder(persona="critic")
    redacted = builder.redact_for_output("secret", DataClassification.CONFIDENTIAL)
    assert redacted == "[REDACTED_CLASSIFICATION]"
    assert builder.log_allowed(DataClassification.RESTRICTED) is False


@pytest.mark.unit
def test_apply_protection_redacts_payload():
    builder = SecureContextBuilder(persona="critic")
    protected = builder.apply_protection({"text": "restricted memo", "classification": DataClassification.CONFIDENTIAL})
    assert protected["redacted"] is True
    assert protected["text"] == "[REDACTED_CLASSIFICATION]"


@pytest.mark.unit
def test_classify_text_internal_markers_and_passthrough():
    builder = SecureContextBuilder(persona="soc")
    assert builder.classify_text("internal only playbook") == DataClassification.CONFIDENTIAL
    assert builder.redact_for_output("visible", DataClassification.INTERNAL) == "visible"
    unchanged = builder.apply_protection({"text": "routine note", "classification": DataClassification.INTERNAL})
    assert unchanged == {"text": "routine note", "classification": DataClassification.INTERNAL}
