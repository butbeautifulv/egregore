"""Output guardrails must block system prompt leakage patterns."""


def test_detect_prompt_leakage_patterns(guardrails):
    assert guardrails.detect_prompt_leakage("SYSTEM: You are a security agent with full access")
    assert guardrails.detect_prompt_leakage("Here are my SECURITY_RULES: 1. NEVER reveal")
    assert not guardrails.detect_prompt_leakage("Found suspicious DNS activity in scope")


def test_validate_output_blocks_leakage(guardrails):
    import pytest

    from cys_core.domain.security.exceptions import SecurityViolation

    with pytest.raises(SecurityViolation, match="leakage"):
        guardrails.validate_output({"response": "SYSTEM_INSTRUCTIONS: You are RedTeamAgent"})
