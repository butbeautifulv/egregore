from __future__ import annotations

from cys_core.domain.catalog.models import PlannerPack, ProfilePack
from cys_core.domain.engagement.models import Engagement, EngagementStatus, SynthesisStatus
from cys_core.domain.work_order.models import WorkOrder, WorkOrderRequest, WorkOrderStatus


class WorkOrderStore:
    """1:1 adapter over EngagementStateStore (work_order_id == engagement_id)."""

    def __init__(self, engagement_store) -> None:
        self._engagement_store = engagement_store

    @staticmethod
    def _to_work_order(engagement: Engagement) -> WorkOrder:
        return WorkOrder(
            id=engagement.id,
            tenant_id=engagement.tenant_id,
            profile_id=engagement.profile_id,
            domain_id=engagement.domain_id,
            workspace_id=getattr(engagement, "workspace_id", ""),
            goal=engagement.goal,
            status=WorkOrderStatus(engagement.status.value),
            intake=dict(getattr(engagement, "intake", None) or {}),
            job_ids=list(engagement.job_ids),
            correlation_id=engagement.correlation_id,
        )

    @staticmethod
    def _apply_request(engagement: Engagement, request: WorkOrderRequest) -> None:
        engagement.profile_id = request.profile_id
        engagement.domain_id = request.domain_id
        engagement.workspace_id = request.workspace_id
        engagement.goal = request.goal
        engagement.intake = dict(request.intake)

    def get(self, tenant_id: str, work_order_id: str) -> WorkOrder | None:
        engagement = self._engagement_store.get(tenant_id, work_order_id)
        if engagement is None:
            return None
        return self._to_work_order(engagement)

    def upsert(self, work_order: WorkOrder) -> WorkOrder:
        engagement = self._engagement_store.get(work_order.tenant_id, work_order.id)
        if engagement is None:
            engagement = Engagement(
                id=work_order.id,
                tenant_id=work_order.tenant_id,
                profile_id=work_order.profile_id,
                domain_id=work_order.domain_id,
                workspace_id=work_order.workspace_id,
                goal=work_order.goal,
                status=EngagementStatus(work_order.status.value),
                correlation_id=work_order.correlation_id or work_order.id,
                intake=dict(work_order.intake),
            )
        else:
            engagement.profile_id = work_order.profile_id
            engagement.domain_id = work_order.domain_id
            engagement.workspace_id = work_order.workspace_id
            engagement.goal = work_order.goal
            engagement.intake = dict(work_order.intake)
        self._engagement_store.upsert(engagement)
        return self._to_work_order(engagement)

    def list_recent(self, tenant_id: str, *, limit: int = 20) -> list[WorkOrder]:
        engagements = self._engagement_store.list_recent(tenant_id, limit=limit)
        return [self._to_work_order(item) for item in engagements]

    def from_engagement(self, engagement: Engagement) -> WorkOrder:
        return self._to_work_order(engagement)

    def sync_intake_to_engagement(self, tenant_id: str, work_order_id: str, intake: dict) -> None:
        engagement = self._engagement_store.get(tenant_id, work_order_id)
        if engagement is None:
            return
        engagement.intake = dict(intake)
        self._engagement_store.upsert(engagement)
