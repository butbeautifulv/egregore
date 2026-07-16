from __future__ import annotations

import pytest

from cys_core.domain.engagement.bus_guard import (
    BusGuardLimits,
    GuardCounters,
    TripReason,
    should_trip,
)


@pytest.mark.unit
def test_should_trip_total_jobs() -> None:
    limits = BusGuardLimits(
        max_total_jobs_window=10,
        dedup_trip_threshold=5,
        pingpong_trip_threshold=3,
        noop_churn_threshold=4,
    )
    counters = GuardCounters(total_jobs=10)
    assert should_trip(counters, limits) == TripReason.TOTAL_JOBS


@pytest.mark.unit
def test_should_trip_dedup_hits() -> None:
    limits = BusGuardLimits(
        max_total_jobs_window=100,
        dedup_trip_threshold=5,
        pingpong_trip_threshold=3,
        noop_churn_threshold=4,
    )
    counters = GuardCounters(dedup_hits=5)
    assert should_trip(counters, limits) == TripReason.DEDUP_HITS


@pytest.mark.unit
def test_should_trip_pingpong() -> None:
    limits = BusGuardLimits(
        max_total_jobs_window=100,
        dedup_trip_threshold=50,
        pingpong_trip_threshold=3,
        noop_churn_threshold=4,
    )
    counters = GuardCounters(pingpong_cycles=3)
    assert should_trip(counters, limits) == TripReason.PINGPONG


@pytest.mark.unit
def test_should_trip_noop_churn() -> None:
    limits = BusGuardLimits(
        max_total_jobs_window=100,
        dedup_trip_threshold=50,
        pingpong_trip_threshold=30,
        noop_churn_threshold=4,
    )
    counters = GuardCounters(noop_publishes=4)
    assert should_trip(counters, limits) == TripReason.NOOP_CHURN


@pytest.mark.unit
def test_should_trip_returns_none_when_under_limits() -> None:
    limits = BusGuardLimits(
        max_total_jobs_window=100,
        dedup_trip_threshold=50,
        pingpong_trip_threshold=30,
        noop_churn_threshold=40,
    )
    counters = GuardCounters(total_jobs=1, dedup_hits=1, pingpong_cycles=1, noop_publishes=1)
    assert should_trip(counters, limits) is None
