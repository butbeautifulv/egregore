from __future__ import annotations

from typing import Protocol

from cys_core.domain.engagement.models import Engagement
from cys_core.domain.work_order.models import WorkOrder


class WorkOrderStorePort(Protocol):
    def get(self, tenant_id: str, work_order_id: str) -> WorkOrder | None: ...

    def upsert(self, work_order: WorkOrder) -> WorkOrder: ...

    def list_recent(self, tenant_id: str, *, limit: int = 20) -> list[WorkOrder]: ...

    def from_engagement(self, engagement: Engagement) -> WorkOrder: ...

    def sync_intake_to_engagement(self, tenant_id: str, work_order_id: str, intake: dict) -> None: ...
