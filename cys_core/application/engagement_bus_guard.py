from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import structlog

from cys_core.application.bus_guard_config import BusGuardConfig

logger = structlog.get_logger(__name__)


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


class EngagementBusGuard:
    """Redis-backed engagement loop circuit breaker (successful churn, not exceptions)."""

    KEY_PREFIX = "cys:bus:guard:"

    def __init__(self, *, config: BusGuardConfig) -> None:
        self._config = config
        self._window = config.guard_window_seconds
        self._redis: Any = None
        self._memory: dict[str, dict[str, Any]] = {}

    def _ensure_redis(self) -> bool:
        if self._redis is not None:
            try:
                self._redis.ping()
                return True
            except Exception:
                self._redis = None
        try:
            import redis

            client = redis.Redis.from_url(self._config.redis_url, decode_responses=True)
            client.ping()
            self._redis = client
            return True
        except Exception:
            self._redis = None
            return False

    def _key(self, engagement_id: str, suffix: str) -> str:
        return f"{self.KEY_PREFIX}{engagement_id}:{suffix}"

    def _incr(self, engagement_id: str, suffix: str, *, amount: int = 1) -> int:
        if self._ensure_redis():
            try:
                key = self._key(engagement_id, suffix)
                value = int(self._redis.incrby(key, amount))
                self._redis.expire(key, self._window)
                return value
            except Exception as exc:
                logger.warning("engagement_bus_guard_redis_failed", error=str(exc))
                self._redis = None
        bucket = self._memory.setdefault(engagement_id, {})
        now = time.time()
        entry = bucket.setdefault(suffix, {"count": 0, "expires": now + self._window})
        if now > entry["expires"]:
            entry["count"] = 0
            entry["expires"] = now + self._window
        entry["count"] += amount
        return int(entry["count"])

    def _get_count(self, engagement_id: str, suffix: str) -> int:
        if self._ensure_redis():
            try:
                raw = self._redis.get(self._key(engagement_id, suffix))
                return int(raw or 0)
            except Exception:
                self._redis = None
        bucket = self._memory.get(engagement_id, {})
        entry = bucket.get(suffix)
        if not entry:
            return 0
        if time.time() > entry["expires"]:
            return 0
        return int(entry["count"])

    def is_tripped(self, engagement_id: str) -> bool:
        if not engagement_id:
            return False
        if self._ensure_redis():
            try:
                return bool(self._redis.get(self._key(engagement_id, "tripped")))
            except Exception:
                self._redis = None
        return bool(self._memory.get(engagement_id, {}).get("tripped"))

    def trip(self, engagement_id: str, reason: TripReason) -> bool:
        """Mark engagement tripped idempotently. Returns True if newly tripped."""
        if not engagement_id or self.is_tripped(engagement_id):
            return False
        if self._ensure_redis():
            try:
                inserted = self._redis.set(
                    self._key(engagement_id, "tripped"),
                    reason.value,
                    nx=True,
                    ex=self._window * 2,
                )
                return bool(inserted)
            except Exception:
                self._redis = None
        bucket = self._memory.setdefault(engagement_id, {})
        if bucket.get("tripped"):
            return False
        bucket["tripped"] = reason.value
        return True

    def counters(self, engagement_id: str) -> GuardCounters:
        return GuardCounters(
            total_jobs=self._get_count(engagement_id, "enqueue"),
            dedup_hits=self._get_count(engagement_id, "dedup"),
            pingpong_cycles=self._get_count(engagement_id, "pingpong"),
            noop_publishes=self._get_count(engagement_id, "noop"),
        )

    def should_trip(self, engagement_id: str) -> TripReason | None:
        if not engagement_id or self.is_tripped(engagement_id):
            return None
        cfg = self._config
        counts = self.counters(engagement_id)
        if counts.total_jobs >= cfg.max_total_jobs_window:
            return TripReason.TOTAL_JOBS
        if counts.dedup_hits >= cfg.dedup_trip_threshold:
            return TripReason.DEDUP_HITS
        if counts.pingpong_cycles >= cfg.pingpong_trip_threshold:
            return TripReason.PINGPONG
        if counts.noop_publishes >= cfg.noop_churn_threshold:
            return TripReason.NOOP_CHURN
        return None

    def record_enqueue(self, engagement_id: str, recipient: str, fingerprint: str = "") -> None:
        if not engagement_id:
            return
        self._incr(engagement_id, "enqueue")
        self._track_pingpong(engagement_id, recipient)

    def record_dedup_hit(self, engagement_id: str, fingerprint: str) -> None:
        if not engagement_id:
            return
        self._incr(engagement_id, "dedup")
        if fingerprint:
            self._incr(engagement_id, f"dedup:{fingerprint[:16]}")

    def record_noop_publish(self, engagement_id: str, persona: str) -> None:
        if not engagement_id:
            return
        self._incr(engagement_id, "noop")
        logger.debug("engagement_noop_churn", engagement_id=engagement_id, persona=persona)

    def _track_pingpong(self, engagement_id: str, recipient: str) -> None:
        if not recipient:
            return
        history_key = self._key(engagement_id, "personas")
        if self._ensure_redis():
            try:
                self._redis.lpush(history_key, recipient)
                self._redis.ltrim(history_key, 0, 7)
                self._redis.expire(history_key, self._window)
                recent = self._redis.lrange(history_key, 0, 3)
                if len(recent) >= 3 and recent[0] == recent[2] and recent[0] != recent[1]:
                    self._incr(engagement_id, "pingpong")
                return
            except Exception:
                self._redis = None
        bucket = self._memory.setdefault(engagement_id, {})
        history: list[str] = bucket.setdefault("personas", [])
        history.insert(0, recipient)
        del history[4:]
        if len(history) >= 3 and history[0] == history[2] and history[0] != history[1]:
            self._incr(engagement_id, "pingpong")


_guard: EngagementBusGuard | None = None


def configure_engagement_bus_guard(guard: EngagementBusGuard) -> None:
    global _guard
    _guard = guard


def get_engagement_bus_guard() -> EngagementBusGuard:
    if _guard is None:
        raise RuntimeError("EngagementBusGuard not configured; initialize via bootstrap.container")
    return _guard


def reset_engagement_bus_guard() -> None:
    global _guard
    _guard = None
