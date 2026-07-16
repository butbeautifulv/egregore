"""Thin alias router — session creation delegates to runs handlers."""

from __future__ import annotations

from interfaces.api.runs import create_session, router

__all__ = ["create_session", "router"]
