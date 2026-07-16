from __future__ import annotations

from typing import Protocol


class AttachmentStorePort(Protocol):
    def save(self, tenant_id: str, run_id: str, filename: str, data: bytes) -> str: ...

    def list_paths(self, tenant_id: str, run_id: str) -> list[str]: ...
