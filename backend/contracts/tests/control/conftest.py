from __future__ import annotations

import pytest

from cys_core.application.bus_guard_config import BusGuardConfig
from cys_core.application.engagement_bus_guard import (
    EngagementBusGuard,
    configure_engagement_bus_guard,
    reset_engagement_bus_guard,
)


@pytest.fixture(autouse=True)
def _engagement_bus_guard() -> None:
    reset_engagement_bus_guard()
    configure_engagement_bus_guard(
        EngagementBusGuard(
            config=BusGuardConfig(
                max_total_jobs_window=50,
                dedup_trip_threshold=5,
                pingpong_trip_threshold=3,
                noop_churn_threshold=10,
                guard_window_seconds=600,
                redis_url="redis://localhost:6379/0",
            )
        )
    )
    yield
    reset_engagement_bus_guard()
