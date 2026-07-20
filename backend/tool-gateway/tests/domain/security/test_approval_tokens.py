from __future__ import annotations

import time

import pytest

from cys_core.domain.security.approval_tokens import args_hash, mint_approval_token, verify_approval_token


@pytest.mark.unit
def test_mint_and_verify_roundtrip():
    token = mint_approval_token(
        tool_name="run_playbook", tool_args={"playbook_id": "p-1"}, ttl_s=60, secret=b"secret"
    )
    claims = verify_approval_token(token, secret=b"secret")
    assert claims is not None
    assert claims.tool_name == "run_playbook"
    assert claims.args_hash == args_hash({"playbook_id": "p-1"})
    assert claims.expired is False


@pytest.mark.unit
def test_verify_rejects_wrong_secret():
    token = mint_approval_token(tool_name="run_playbook", tool_args={"playbook_id": "p-1"}, ttl_s=60, secret=b"secret")
    assert verify_approval_token(token, secret=b"wrong-secret") is None


@pytest.mark.unit
def test_verify_rejects_tampered_payload():
    token = mint_approval_token(tool_name="run_playbook", tool_args={"playbook_id": "p-1"}, ttl_s=60, secret=b"secret")
    body, signature = token.split(".", 1)
    tampered_body = body[:-1] + ("A" if body[-1] != "A" else "B")
    assert verify_approval_token(f"{tampered_body}.{signature}", secret=b"secret") is None


@pytest.mark.unit
def test_verify_rejects_expired_token():
    token = mint_approval_token(tool_name="run_playbook", tool_args={"playbook_id": "p-1"}, ttl_s=-1, secret=b"secret")
    assert verify_approval_token(token, secret=b"secret") is None


@pytest.mark.unit
def test_verify_rejects_malformed_token():
    assert verify_approval_token("not-a-valid-token", secret=b"secret") is None
    assert verify_approval_token("", secret=b"secret") is None


@pytest.mark.unit
def test_expired_property_reflects_wall_clock():
    token = mint_approval_token(
        tool_name="run_playbook", tool_args={"playbook_id": "p-1"}, ttl_s=0.05, secret=b"secret"
    )
    claims = verify_approval_token(token, secret=b"secret")
    assert claims is not None
    time.sleep(0.1)
    assert claims.expired is True


@pytest.mark.unit
def test_args_hash_binds_the_token_to_the_exact_args_it_was_minted_for():
    """The whole point of this token: approving one call must not silently approve a
    substituted, more dangerous call for the same tool. Verifying the token alone isn't
    enough — the caller must also recompute args_hash from the retry's actual args and
    compare, exactly as ToolsContainer._resolve_hitl_decision does."""
    token = mint_approval_token(
        tool_name="run_playbook", tool_args={"playbook_id": "p-1", "target": "host-a"}, ttl_s=60, secret=b"secret"
    )
    claims = verify_approval_token(token, secret=b"secret")
    assert claims is not None
    assert claims.args_hash != args_hash({"playbook_id": "p-1", "target": "host-b"})
