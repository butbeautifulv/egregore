from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TripReason(StrEnum):
    TOTAL_JOBS = "total_jobs"
    DEDUP_HITS = "dedup_hits"
    PINGPONG = "pingpong"
    NOOP_CHURN = "noop_churn"


@dataclass(frozen=True)
class GuardCounters:
    total_jobs: int = 0
    dedup_hits: int = 0
    pingpong_cycles: int = 0
    noop_publishes: int = 0


@dataclass(frozen=True)
class BusGuardLimits:
    max_total_jobs_window: int
    dedup_trip_threshold: int
    pingpong_trip_threshold: int
    noop_churn_threshold: int


def should_trip(counters: GuardCounters, limits: BusGuardLimits) -> TripReason | None:
    if counters.total_jobs >= limits.max_total_jobs_window:
        return TripReason.TOTAL_JOBS
    if counters.dedup_hits >= limits.dedup_trip_threshold:
        return TripReason.DEDUP_HITS
    if counters.pingpong_cycles >= limits.pingpong_trip_threshold:
        return TripReason.PINGPONG
    if counters.noop_publishes >= limits.noop_churn_threshold:
        return TripReason.NOOP_CHURN
    return None
