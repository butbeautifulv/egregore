from __future__ import annotations

from pathlib import Path

import pytest

from cys_core.infrastructure.runs.attachment_store import FilesystemAttachmentStore


@pytest.mark.unit
def test_save_rejects_path_traversal_in_tenant_id(tmp_path):
    store = FilesystemAttachmentStore(root=str(tmp_path))
    outside = tmp_path.parent / "escaped.bin"
    outside.unlink(missing_ok=True)

    store.save("../../../../tmp/evil", "run-1", "note.txt", b"payload")

    assert not outside.exists()
    written = list(tmp_path.rglob("note.txt"))
    assert len(written) == 1
    assert tmp_path in written[0].resolve().parents


@pytest.mark.unit
def test_save_rejects_path_traversal_in_run_id(tmp_path):
    store = FilesystemAttachmentStore(root=str(tmp_path))

    saved = store.save("tenant-1", "../../etc", "note.txt", b"payload")

    assert str(tmp_path.resolve()) in saved
    assert ".." not in Path(saved).relative_to(tmp_path.resolve()).parts


@pytest.mark.unit
def test_save_and_list_round_trip(tmp_path):
    store = FilesystemAttachmentStore(root=str(tmp_path))

    store.save("tenant-1", "run-1", "note.txt", b"hello")
    paths = store.list_paths("tenant-1", "run-1")

    assert len(paths) == 1
    assert paths[0].endswith("note.txt")
