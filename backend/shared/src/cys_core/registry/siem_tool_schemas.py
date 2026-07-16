from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InvestigateIncidentInput(BaseModel):
    incident_id: str = Field(..., description="MaxPatrol SIEM incident UUID from payload")
    events_limit: int = 20
    include_raw_events: bool = True
    include_ioc_checks: bool = False
    include_target_assets: bool = False


class ListIncidentsInput(BaseModel):
    filter_body: dict[str, Any] | None = None
    filter_time_type: str = "creation"
    limit: int = 50
    offset: int = 0


class SearchEventsInput(BaseModel):
    where: str = Field(..., description="PDQL where clause")
    limit: int = 50
    offset: int = 0
    time_from: int | None = None
    time_to: int | None = None
    incident_id: str | None = None
    group_ids: list[str] | None = None


class GetEventByUuidInput(BaseModel):
    event_uuid: str = Field(..., description="SIEM event UUID")
    time_from: int | None = None
    time_to: int | None = None


class GenericSiemToolInput(BaseModel):
    model_config = ConfigDict(extra="allow")
