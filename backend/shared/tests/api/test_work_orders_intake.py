from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.application.use_cases.start_work_order import StartWorkOrder, WorkOrderValidationError
from cys_core.domain.work_order.models import WorkOrderRequest
from cys_core.infrastructure.work_order.adapter import WorkOrderStore


@pytest.mark.unit
def test_work_order_intake_requires_goal() -> None:
    store = WorkOrderStore(MagicMock())
    start = StartWorkOrder(work_order_store=store, start_engagement=MagicMock(), agent_catalog=MagicMock())
    with pytest.raises(WorkOrderValidationError):
        start._validate_intake(WorkOrderRequest(intake={}))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_work_orders_returns_personas_and_updated_at(monkeypatch) -> None:
    from datetime import UTC, datetime

    from cys_core.domain.engagement.models import Engagement, EngagementStatus
    from interfaces.api.work_orders import list_work_orders

    store = MagicMock()
    updated = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
    engagement = Engagement(
        id="wo-1",
        tenant_id="default",
        goal="triage ransomware",
        status=EngagementStatus.RUNNING,
        completed_personas=["soc", "forensics"],
        failed_personas=["malware"],
    )
    store.list_recent_page.return_value = ([(engagement, updated)], None)
    monkeypatch.setattr(
        "interfaces.api.work_orders.get_container",
        lambda: MagicMock(get_engagement_state_store=lambda: store),
    )

    result = await list_work_orders(tenant_id="default", limit=20)
    assert len(result.work_orders) == 1
    item = result.work_orders[0]
    assert item.work_order_id == "wo-1"
    assert item.goal == "triage ransomware"
    assert item.completed_personas == ["soc", "forensics"]
    assert item.failed_personas == ["malware"]
    assert item.updated_at == updated
    assert result.next_cursor is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_work_orders_invalid_cursor_returns_400(monkeypatch) -> None:
    from fastapi import HTTPException

    from cys_core.infrastructure.engagement.list_cursor import InvalidListCursor
    from interfaces.api.work_orders import list_work_orders

    store = MagicMock()
    store.list_recent_page.side_effect = InvalidListCursor("bad")
    monkeypatch.setattr(
        "interfaces.api.work_orders.get_container",
        lambda: MagicMock(get_engagement_state_store=lambda: store),
    )

    with pytest.raises(HTTPException) as exc_info:
        await list_work_orders(tenant_id="default", limit=20, cursor="bad")
    assert exc_info.value.status_code == 400


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_work_orders_postgres_includes_updated_at(monkeypatch) -> None:
    from datetime import UTC, datetime

    from cys_core.domain.engagement.models import Engagement, EngagementStatus
    from interfaces.api.work_orders import list_work_orders

    updated = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
    engagement = Engagement(
        id="wo-2",
        tenant_id="default",
        goal="phishing review",
        status=EngagementStatus.CLOSED,
        completed_personas=["soc"],
    )
    store = MagicMock()
    store.list_recent_page.return_value = [(engagement, updated)], None
    monkeypatch.setattr(
        "interfaces.api.work_orders.get_container",
        lambda: MagicMock(get_engagement_state_store=lambda: store),
    )

    result = await list_work_orders(tenant_id="default", limit=20)
    item = result.work_orders[0]
    assert item.work_order_id == "wo-2"
    assert item.updated_at == updated
