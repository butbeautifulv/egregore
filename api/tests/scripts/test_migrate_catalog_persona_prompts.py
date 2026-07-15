import json

import pytest

from scripts.migrate_catalog_persona_prompts import (
    migrate_agent_payload,
    migrate_profile_payload,
)


@pytest.mark.unit
def test_migrate_agent_payload_strips_baked_rules():
    payload = {
        "name": "soc",
        "role": "worker",
        "system_prompt": "SYSTEM_INSTRUCTIONS:\nYou are SocAgent.\n\nGLOBAL_RULES:\nold\n\nSECURITY_RULES:\n1. rule",
        "system_prompt_digest": "deadbeef",
    }
    migrated = migrate_agent_payload(payload)
    assert migrated["persona_prompt"] == "You are SocAgent."
    assert migrated["system_prompt"] == ""
    assert migrated["system_prompt_digest"] != "deadbeef"
    assert "GLOBAL_RULES:" in json.dumps(migrated) or migrated["persona_prompt"]


@pytest.mark.unit
def test_migrate_profile_payload_clears_global_rules():
    migrated = migrate_profile_payload({"id": "cybersec-soc", "name": "SOC", "global_rules": "legacy"})
    assert migrated["global_rules"] == ""
