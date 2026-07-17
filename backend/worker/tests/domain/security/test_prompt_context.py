import pytest

from cys_core.domain.security.prompt_context import (
    REFUSAL_MESSAGE,
    SECURITY_RULES_BLOCK,
    build_trusted_system_context,
    build_untrusted_data,
    compute_system_digest,
    format_system_prompt,
    wrap_user_data,
)


@pytest.mark.unit
def test_refusal_message_in_security_rules_block():
    assert REFUSAL_MESSAGE in SECURITY_RULES_BLOCK


@pytest.mark.unit
def test_compute_system_digest_is_stable():
    text = format_system_prompt("persona", "GLOBAL_RULES:\nrules", "SECURITY_RULES:\n1. rule")
    assert compute_system_digest(text) == compute_system_digest(text)


@pytest.mark.unit
def test_build_trusted_system_context_empty_global_rules():
    ctx = build_trusted_system_context("You are agent.", "")
    assert "SYSTEM_INSTRUCTIONS:" in ctx.text
    assert "SECURITY_RULES:" in ctx.text
    assert ctx.digest == compute_system_digest(ctx.text)


@pytest.mark.unit
def test_wrap_user_data_includes_source():
    wrapped = wrap_user_data("payload", source="agent_bus")
    assert wrapped.startswith("USER_DATA_TO_PROCESS [source=agent_bus]")
    assert '<untrusted_data source="agent_bus">' in wrapped


@pytest.mark.unit
def test_format_system_prompt_uses_default_security_block():
    text = format_system_prompt("persona", "GLOBAL_RULES:\nrules", "custom rules without prefix")
    assert SECURITY_RULES_BLOCK in text


@pytest.mark.unit
def test_build_untrusted_data():
    data = build_untrusted_data("raw", "clean", source="user")
    assert data.raw == "raw"
    assert data.sanitized == "clean"
    assert data.wrapped == wrap_user_data("clean", source="user")
