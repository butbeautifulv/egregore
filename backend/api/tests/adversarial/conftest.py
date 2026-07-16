"""Adversarial tests inherit shared fixtures from tests/conftest.py."""

from __future__ import annotations

import pytest

from cys_core.domain.security.sanitizer import InputSanitizer

pytestmark = pytest.mark.adversarial


@pytest.fixture
def sanitizer() -> InputSanitizer:
    return InputSanitizer()
