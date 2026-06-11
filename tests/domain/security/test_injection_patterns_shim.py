import pytest

from cys_core.domain.security import injection_patterns as shim


@pytest.mark.unit
def test_injection_patterns_shim_reexports():
    assert shim.HARD_INJECTION_PATTERNS
    assert shim.SOFT_INJECTION_PATTERNS
    assert shim.INJECTION_PATTERNS == shim.HARD_INJECTION_PATTERNS + shim.SOFT_INJECTION_PATTERNS
    assert shim.FUZZY_KEYWORDS
    assert shim.BASE64_TOKEN.pattern
    assert shim.HEX_TOKEN.pattern
