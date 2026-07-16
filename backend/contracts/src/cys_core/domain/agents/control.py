"""Platform control-plane personas — single source of truth (ADR-005)."""

from __future__ import annotations

CONTROL_PERSONAS: frozenset[str] = frozenset({"planner", "critic", "coordinator"})

# Platform agents spawnable without workspace fork (read-only / advisory).
PLATFORM_READONLY_PERSONAS: frozenset[str] = frozenset(
    {"consultant", "intel", "planner", "critic", "coordinator"},
)


def is_control_persona(name: str) -> bool:
    return name in CONTROL_PERSONAS


def is_platform_readonly_persona(name: str) -> bool:
    return name in PLATFORM_READONLY_PERSONAS
