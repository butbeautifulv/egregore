from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SyncScanInventoryInput(BaseModel):
    scan_id: int = Field(..., description="Nessus scan ID")
    force_refresh: bool = False
    export_format: str = "nessus"


class WaitForScanInput(BaseModel):
    scan_id: int = Field(..., description="Nessus scan ID")
    poll_interval: int = 30
    timeout: int = 7200


class LookupAssetByIpInput(BaseModel):
    ip: str = Field(..., description="Asset IP address")


class GetAssetFindingsInput(BaseModel):
    ip: str = Field(..., description="Asset IP address")
    min_severity: int | None = None
    limit: int = 100


class SearchInventoryInput(BaseModel):
    ip_contains: str | None = None
    os_contains: str | None = None
    min_critical: int | None = None
    min_high: int | None = None
    limit: int = 50


class CreateScanInput(BaseModel):
    name: str
    text_targets: str = Field(..., description="IPs/hostnames, comma-separated")
    template_uuid: str | None = None
    template_name: str = "advanced"
    description: str = ""


class LaunchScanInput(BaseModel):
    scan_id: int = Field(..., description="Nessus scan ID")


class GenericNessusToolInput(BaseModel):
    model_config = ConfigDict(extra="allow")
