"""Assemble trusted system prompts from persona + immutable backend rules."""

from __future__ import annotations

from cys_core.domain.security.immutable_rules import GLOBAL_RULES_BODY
from cys_core.domain.security.prompt_context import TrustedSystemContext, build_trusted_system_context

LANGUAGE_SUFFIX = (
    "\n\nLanguage: You may think in English, but you MUST answer in Russian. "
    "Keep JSON field names in English; values should be in Russian."
)

_SECTION_MARKERS = ("GLOBAL_RULES:", "SECURITY_RULES:")
_SYSTEM_INSTRUCTIONS_PREFIX = "SYSTEM_INSTRUCTIONS:"


def extract_persona_prompt(stored: str) -> str:
    """Strip trusted rule sections from legacy or API-supplied full prompts."""
    text = stored.strip()
    if not text:
        return ""

    if text.startswith("USER_DATA_TO_PROCESS"):
        start = text.find("<untrusted_data")
        end = text.rfind("</untrusted_data>")
        if start != -1 and end != -1:
            inner = text[text.find(">", start) + 1 : end]
            text = inner.strip()

    if text.startswith(_SYSTEM_INSTRUCTIONS_PREFIX):
        text = text[len(_SYSTEM_INSTRUCTIONS_PREFIX) :].lstrip("\n")

    for marker in _SECTION_MARKERS:
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx]

    text = text.strip()
    if text.endswith(LANGUAGE_SUFFIX):
        text = text[: -len(LANGUAGE_SUFFIX)].rstrip()
    return text.strip()


def _apply_language_suffix(persona: str, *, language: str | None) -> str:
    body = persona.strip()
    if not body or language != "ru":
        return body
    if body.endswith(LANGUAGE_SUFFIX):
        return body
    return f"{body}{LANGUAGE_SUFFIX}"


def assemble_trusted_system_context(
    persona: str,
    *,
    language: str | None = "ru",
) -> TrustedSystemContext:
    """Always inject backend GLOBAL_RULES and SECURITY_RULES."""
    persona_body = _apply_language_suffix(extract_persona_prompt(persona), language=language)
    return build_trusted_system_context(persona_body, GLOBAL_RULES_BODY)


def resolve_persona_prompt(entry: object) -> str:
    """Resolve persona text from a catalog entry (persona_prompt or legacy system_prompt)."""
    persona_prompt = getattr(entry, "persona_prompt", "") or ""
    if persona_prompt.strip():
        return extract_persona_prompt(persona_prompt)
    system_prompt = getattr(entry, "system_prompt", "") or ""
    return extract_persona_prompt(system_prompt)


def had_embedded_rule_sections(text: str) -> bool:
    """True when input contained GLOBAL_RULES or SECURITY_RULES markers."""
    upper = text.upper()
    return any(marker in upper for marker in _SECTION_MARKERS)


def strip_language_suffix(text: str) -> str:
    """Remove backend language suffix from persona text."""
    body = text.strip()
    if body.endswith(LANGUAGE_SUFFIX):
        return body[: -len(LANGUAGE_SUFFIX)].rstrip()
    return body
