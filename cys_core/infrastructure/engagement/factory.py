from __future__ import annotations

from cys_core.application.ports.engagement_egress import EngagementEgressPort
from cys_core.infrastructure.engagement.memory_egress import MemoryEngagementEgress
from cys_core.infrastructure.engagement.redis_egress import RedisEngagementEgress

_engagement_egress: EngagementEgressPort | None = None


def get_engagement_egress(settings) -> EngagementEgressPort:
    global _engagement_egress
    if _engagement_egress is not None:
        return _engagement_egress
    if settings.stage == "test":
        _engagement_egress = MemoryEngagementEgress()
        return _engagement_egress
    redis_egress = RedisEngagementEgress(settings=settings)
    _engagement_egress = redis_egress if redis_egress.active_backend == "redis" else MemoryEngagementEgress()
    return _engagement_egress


def reset_engagement_egress_cache() -> None:
    global _engagement_egress
    _engagement_egress = None
