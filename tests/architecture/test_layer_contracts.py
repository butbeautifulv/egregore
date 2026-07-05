from __future__ import annotations

"""Shrink-only allowlist regression tests for architecture import boundaries."""

import scripts.verify_import_boundaries as boundaries


def _allowlist_size(allowlist: frozenset[str]) -> int:
    return len(allowlist)


# Snapshot sizes — decrease only via intentional debt paydown; never grow without review.
_EXPECTED_ALLOWLIST_SIZES: dict[str, int] = {
    "ALLOWLIST_APPLICATION_INTERFACES": 0,
    "ALLOWLIST_APPLICATION_BOOTSTRAP": 0,
    "ALLOWLIST_APPLICATION_INFRASTRUCTURE": 0,
    "ALLOWLIST_APPLICATION_REGISTRY": 0,
    "ALLOWLIST_APPLICATION_OBSERVABILITY": 0,
    "ALLOWLIST_APPLICATION_RUNTIME": 0,
    "ALLOWLIST_INFRASTRUCTURE_INTERFACES": 0,
    "ALLOWLIST_REGISTRY_INTERFACES": 0,
    "ALLOWLIST_INTERFACES_API_INFRASTRUCTURE": 1,
    "ALLOWLIST_INFRASTRUCTURE_USE_CASES": 0,
    "ALLOWLIST_BOOTSTRAP_INTERFACES": 38,
}


def test_allowlist_sizes_shrink_only_contract():
    for name, expected in _EXPECTED_ALLOWLIST_SIZES.items():
        allowlist = getattr(boundaries, name)
        actual = _allowlist_size(allowlist)
        assert actual <= expected, (
            f"{name} grew to {actual} (max {expected}). "
            "Fix violations instead of expanding allowlists."
        )


def test_application_allowlists_stay_empty():
    assert boundaries.ALLOWLIST_APPLICATION_BOOTSTRAP == frozenset()
    assert boundaries.ALLOWLIST_APPLICATION_INFRASTRUCTURE == frozenset()
    assert boundaries.ALLOWLIST_APPLICATION_OBSERVABILITY == frozenset()
    assert boundaries.ALLOWLIST_APPLICATION_REGISTRY == frozenset()


def test_interfaces_api_infra_allowlist_only_app_health():
    assert boundaries.ALLOWLIST_INTERFACES_API_INFRASTRUCTURE == frozenset({"interfaces/api/app.py"})


def test_infrastructure_use_cases_allowlist_empty():
    assert boundaries.ALLOWLIST_INFRASTRUCTURE_USE_CASES == frozenset()


def test_new_gate_checks_are_wired():
    """Document expected gate checks — API routers use container only."""
    api_violations = boundaries.check_interfaces_api_no_infrastructure()
    assert isinstance(api_violations, list)
    assert api_violations == []

    use_case_violations = boundaries.check_infrastructure_no_use_cases()
    assert use_case_violations == []
