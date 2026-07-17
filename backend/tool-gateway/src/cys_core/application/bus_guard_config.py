from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BusGuardConfig:
    max_total_jobs_window: int
    dedup_trip_threshold: int
    pingpong_trip_threshold: int
    noop_churn_threshold: int
    guard_window_seconds: int
    redis_url: str
    max_jobs_per_engagement: int = 20
