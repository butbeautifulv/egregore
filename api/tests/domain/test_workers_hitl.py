from __future__ import annotations

import pytest

from cys_core.domain.workers.hitl import create_approval_id, params_hash


@pytest.mark.unit
def test_create_approval_id_format():
    approval_id = create_approval_id()
    assert approval_id.startswith("appr-")


@pytest.mark.unit
def test_params_hash_stable():
    args = {"query": "dns", "limit": 10}
    assert params_hash(args) == params_hash({"limit": 10, "query": "dns"})
