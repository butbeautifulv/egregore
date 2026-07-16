import pytest

from cys_core.domain.security.a2a import A2AEnvelope, MtlsPeerIdentity, default_mtls_subject


@pytest.mark.unit
def test_default_mtls_subject():
    assert default_mtls_subject("network") == "spiffe://cys-agi/agent/network"


@pytest.mark.unit
def test_mtls_peer_identity_defaults():
    peer = MtlsPeerIdentity(subject="spiffe://cys-agi/agent/critic")
    assert peer.required is True
    assert peer.san is None


@pytest.mark.unit
def test_a2a_envelope_protocol():
    env = A2AEnvelope(
        sender="network",
        recipient="critic",
        type="finding",
        payload={"x": 1},
        timestamp="2026-01-01T00:00:00+00:00",
        signature="abc",
        mtls={"required": True},
    )
    assert env.protocol == "a2a/1.0"
