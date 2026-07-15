from __future__ import annotations

import pytest

from cys_core.application.ports import SandboxConnector
from cys_core.infrastructure.sandbox import LocalSandboxConnector


@pytest.mark.unit
@pytest.mark.asyncio
async def test_local_sandbox_conforms_to_port():
    sandbox: SandboxConnector = LocalSandboxConnector()
    creds = await sandbox.acreate("run-1", "soc")
    assert creds.sandbox_id
    await sandbox.adestroy("run-1")
    assert not sandbox.is_active("run-1")
