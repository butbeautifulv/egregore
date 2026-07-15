from __future__ import annotations

import re
from pathlib import Path

from cys_core.application.ports.attachment_store import AttachmentStorePort
from cys_core.application.runtime_config import get_run_attachments_dir


def _safe_filename(name: str) -> str:
    base = Path(name).name
    return re.sub(r"[^\w.\-]+", "_", base) or "attachment.bin"


def _safe_path_segment(value: str) -> str:
    """Reject anything but a single, traversal-safe path component.

    tenant_id/run_id come straight from request input (URL path, request
    body) and are used as filesystem path segments — unlike filename, they
    were never sanitized, letting a value like "../../etc" escape the
    attachment root (CodeQL py/path-injection).
    """
    segment = re.sub(r"[^\w.\-]+", "_", value) or "_"
    if segment in (".", ".."):
        segment = "_"
    return segment


class FilesystemAttachmentStore:
    def __init__(self, root: str | None = None) -> None:
        self._root = Path(root or get_run_attachments_dir())

    def _run_dir(self, tenant_id: str, run_id: str) -> Path:
        return self._root / _safe_path_segment(tenant_id) / _safe_path_segment(run_id)

    def save(self, tenant_id: str, run_id: str, filename: str, data: bytes) -> str:
        dest_dir = self._run_dir(tenant_id, run_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / _safe_filename(filename)
        dest.write_bytes(data)
        return str(dest.resolve())

    def list_paths(self, tenant_id: str, run_id: str) -> list[str]:
        run_dir = self._run_dir(tenant_id, run_id)
        if not run_dir.is_dir():
            return []
        return [str(p.resolve()) for p in sorted(run_dir.iterdir()) if p.is_file()]
