from __future__ import annotations

from enum import Enum
from functools import total_ordering


@total_ordering
class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, RiskLevel):
            return NotImplemented
        order = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        return order.index(self) < order.index(other)
