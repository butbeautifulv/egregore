from __future__ import annotations

import time

import pytest

from cys_core.domain.security.sandbox_tokens import mint_sandbox_token, verify_sandbox_token


@pytest.mark.unit
def test_mint_and_verify_roundtrip():
    token = mint_sandbox_token(
        run_id="run-1", persona="soc", tenant_id="default", job_id="job-1", ttl_s=60, secret=b"secret"
    )
    claims = verify_sandbox_token(token, secret=b"secret")
    assert claims is not None
    assert claims.run_id == "run-1"
    assert claims.persona == "soc"
    assert claims.tenant_id == "default"
    assert claims.job_id == "job-1"
    assert claims.expired is False


@pytest.mark.unit
def test_verify_rejects_wrong_secret():
    token = mint_sandbox_token(
        run_id="run-1", persona="soc", tenant_id="default", job_id="job-1", ttl_s=60, secret=b"secret"
    )
    assert verify_sandbox_token(token, secret=b"wrong-secret") is None


@pytest.mark.unit
def test_verify_rejects_tampered_payload():
    token = mint_sandbox_token(
        run_id="run-1", persona="soc", tenant_id="default", job_id="job-1", ttl_s=60, secret=b"secret"
    )
    body, signature = token.split(".", 1)
    # Flip a character in the payload without re-signing — must fail signature check.
    tampered_body = body[:-1] + ("A" if body[-1] != "A" else "B")
    assert verify_sandbox_token(f"{tampered_body}.{signature}", secret=b"secret") is None


@pytest.mark.unit
def test_verify_rejects_expired_token():
    token = mint_sandbox_token(
        run_id="run-1", persona="soc", tenant_id="default", job_id="job-1", ttl_s=-1, secret=b"secret"
    )
    assert verify_sandbox_token(token, secret=b"secret") is None


@pytest.mark.unit
def test_verify_rejects_malformed_token():
    assert verify_sandbox_token("not-a-valid-token", secret=b"secret") is None
    assert verify_sandbox_token("", secret=b"secret") is None


@pytest.mark.unit
def test_expired_property_reflects_wall_clock():
    token = mint_sandbox_token(
        run_id="run-1", persona="soc", tenant_id="default", job_id="job-1", ttl_s=0.05, secret=b"secret"
    )
    claims = verify_sandbox_token(token, secret=b"secret")
    assert claims is not None
    time.sleep(0.1)
    assert claims.expired is True
