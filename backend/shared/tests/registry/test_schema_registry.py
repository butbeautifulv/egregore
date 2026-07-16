from __future__ import annotations

import pytest


@pytest.mark.unit
def test_schema_registry_edges():
    from cys_core.registry.schemas import schema_registry

    assert schema_registry.get(None) is None
    assert "CriticResult" in schema_registry.names()
    with pytest.raises(KeyError, match="Unknown schema"):
        schema_registry.get("MissingSchema")
