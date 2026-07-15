from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import structlog.testing

from cys_core.domain.security.sandbox_tokens import verify_sandbox_token
from cys_core.infrastructure.k8s_sandbox import K8sSandboxConnector

_SECRET = b"test-signing-secret"


def _settings_stub(**overrides):
    defaults = dict(
        k8s_namespace="cys-agi",
        k8s_worker_image="cys-agi-worker:latest",
        k8s_sandbox_ttl_seconds=600.0,
        k8s_sandbox_ready_timeout_s=30.0,
        k8s_sandbox_ready_poll_interval_s=0.5,
        k8s_sandbox_credentials_only=False,
        bus_signing_key_bytes=_SECRET,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _batch_api_ready(*, active=1, ready=0, succeeded=0, failed=0) -> MagicMock:
    """A MagicMock BatchV1Api whose read_namespaced_job() reports a running pod."""
    batch_api = MagicMock()
    batch_api.read_namespaced_job.return_value = SimpleNamespace(
        status=SimpleNamespace(active=active, ready=ready, succeeded=succeeded, failed=failed)
    )
    return batch_api


@pytest.mark.unit
def test_k8s_sandbox_creates_and_deletes_job():
    batch_api = _batch_api_ready(active=1)
    connector = K8sSandboxConnector(
        namespace="cys-agi", batch_api=batch_api, settings=_settings_stub(), ready_poll_interval_s=0.0
    )

    creds = connector.create("run-1", "soc")

    assert creds.sandbox_id.startswith("k8s-worker-soc-run-1")
    assert batch_api.create_namespaced_job.called
    assert batch_api.read_namespaced_job.called
    assert connector.is_active("run-1")

    connector.destroy("run-1")

    batch_api.delete_namespaced_job.assert_called_once()
    assert not connector.is_active("run-1")


@pytest.mark.unit
def test_k8s_sandbox_fails_closed_without_api():
    # No batch_api client configured (e.g. kubernetes package missing/misconfigured
    # in-cluster) — the whole point of a security sandbox is that it must never
    # silently execute the agent unsandboxed when it can't actually provision
    # isolation. This used to fall back to LocalSandboxConnector; it must now refuse.
    connector = K8sSandboxConnector(batch_api=None, settings=_settings_stub())

    with pytest.raises(RuntimeError, match="unavailable"):
        connector.create("run-2", "network")

    assert not connector.is_active("run-2")


@pytest.mark.unit
def test_k8s_sandbox_fails_closed_when_pod_never_becomes_ready():
    # Job accepted by the API server but its pod never starts (e.g. no capacity,
    # ImagePullBackOff) — create() must not hand back credentials for a sandbox that
    # doesn't actually exist yet.
    batch_api = _batch_api_ready(active=0, ready=0, succeeded=0, failed=0)
    connector = K8sSandboxConnector(
        namespace="cys-agi",
        batch_api=batch_api,
        settings=_settings_stub(),
        ready_timeout_s=0.05,
        ready_poll_interval_s=0.01,
    )

    with pytest.raises(TimeoutError):
        connector.create("run-3", "soc")

    # Must not leave orphaned bookkeeping or a dangling Job on the failed attempt.
    assert not connector.is_active("run-3")
    batch_api.delete_namespaced_job.assert_called_once()


@pytest.mark.unit
def test_k8s_sandbox_fails_closed_when_pod_fails_before_ready():
    batch_api = _batch_api_ready(active=0, failed=1)
    connector = K8sSandboxConnector(
        namespace="cys-agi", batch_api=batch_api, settings=_settings_stub(), ready_poll_interval_s=0.0
    )

    with pytest.raises(RuntimeError, match="failed before becoming ready"):
        connector.create("run-4", "soc")
    batch_api.delete_namespaced_job.assert_called_once()


@pytest.mark.unit
def test_k8s_sandbox_refuses_to_reuse_active_run_id():
    batch_api = _batch_api_ready(active=1)
    connector = K8sSandboxConnector(
        namespace="cys-agi", batch_api=batch_api, settings=_settings_stub(), ready_poll_interval_s=0.0
    )
    connector.create("run-5", "soc")

    with pytest.raises(RuntimeError, match="already active"):
        connector.create("run-5", "soc")

    # Only one Job actually created — no silent respawn/overwrite of live state.
    assert batch_api.create_namespaced_job.call_count == 1


@pytest.mark.unit
def test_k8s_sandbox_destroy_logs_instead_of_swallowing():
    batch_api = _batch_api_ready(active=1)
    connector = K8sSandboxConnector(
        namespace="cys-agi", batch_api=batch_api, settings=_settings_stub(), ready_poll_interval_s=0.0
    )
    connector.create("run-6", "soc")
    batch_api.delete_namespaced_job.side_effect = RuntimeError("boom: api server unreachable")

    # Must not raise out of destroy() (it's called from a `finally` block), but must
    # not silently swallow the failure either — this is the FIXME from the prior
    # session: a failed Job deletion used to be a bare `except: pass`.
    with structlog.testing.capture_logs() as captured:
        connector.destroy("run-6")

    assert any(entry.get("event") == "k8s_sandbox_job_delete_failed" for entry in captured)
    delete_log = next(entry for entry in captured if entry.get("event") == "k8s_sandbox_job_delete_failed")
    assert delete_log["run_id"] == "run-6"
    assert delete_log["log_level"] == "error"

    # is_active must reflect that bookkeeping was still cleared even though the
    # underlying k8s delete call failed — no state carried over to the next job.
    assert not connector.is_active("run-6")


@pytest.mark.unit
def test_k8s_sandbox_destroy_is_noop_for_unknown_run_id():
    batch_api = _batch_api_ready(active=1)
    connector = K8sSandboxConnector(namespace="cys-agi", batch_api=batch_api, settings=_settings_stub())

    connector.destroy("never-created")

    batch_api.delete_namespaced_job.assert_not_called()


@pytest.mark.unit
def test_k8s_sandbox_credentials_are_short_lived_and_verifiable():
    batch_api = _batch_api_ready(active=1)
    connector = K8sSandboxConnector(
        namespace="cys-agi",
        batch_api=batch_api,
        settings=_settings_stub(k8s_sandbox_ttl_seconds=45.0),
        ttl_seconds=45.0,
        ready_poll_interval_s=0.0,
    )

    creds = connector.create("run-7", "intel", tenant_id="tenant-x")

    claims = verify_sandbox_token(creds.token, secret=_SECRET)
    assert claims is not None
    assert claims.run_id == "run-7"
    assert claims.persona == "intel"
    assert claims.tenant_id == "tenant-x"
    assert claims.job_id == "run-7"
    assert claims.expired is False

    # Wrong secret must not verify — proves this is a real signed token, not a
    # random opaque string like the old `tok-{policy}-{uuid}` placeholder.
    assert verify_sandbox_token(creds.token, secret=b"wrong-secret") is None


@pytest.mark.unit
def test_k8s_sandbox_job_spec_sets_active_deadline_for_ttl_enforcement():
    batch_api = _batch_api_ready(active=1)
    connector = K8sSandboxConnector(
        namespace="cys-agi",
        batch_api=batch_api,
        settings=_settings_stub(),
        ttl_seconds=123.0,
        ready_poll_interval_s=0.0,
    )

    connector.create("run-8", "soc")

    _, kwargs = batch_api.create_namespaced_job.call_args
    body = kwargs["body"]
    # activeDeadlineSeconds is what makes kubelet/job-controller force-kill a hung
    # agent even if nothing on the Python side ever calls destroy().
    assert body["spec"]["activeDeadlineSeconds"] == 123
    assert body["spec"]["backoffLimit"] == 0
    assert body["spec"]["template"]["spec"]["restartPolicy"] == "Never"


@pytest.mark.unit
async def test_k8s_sandbox_async_lifecycle():
    batch_api = _batch_api_ready(active=1)
    connector = K8sSandboxConnector(
        namespace="cys-agi", batch_api=batch_api, settings=_settings_stub(), ready_poll_interval_s=0.0
    )

    creds = await connector.acreate("run-9", "soc")
    assert connector.is_active("run-9")

    await connector.adestroy("run-9")
    assert not connector.is_active("run-9")
    assert creds.token


@pytest.mark.unit
def test_k8s_sandbox_credentials_only_skips_job_creation():
    """Discovery F: RunWorkerJob.execute() running inside a pod that
    K8sExecutionBackend already created for this run_id must not create a
    second, parasitic Job when it calls sandbox.acreate() for token minting."""
    batch_api = MagicMock()
    connector = K8sSandboxConnector(
        namespace="cys-agi",
        batch_api=batch_api,
        settings=_settings_stub(k8s_sandbox_credentials_only=True),
    )

    creds = connector.create("run-10", "soc")

    batch_api.create_namespaced_job.assert_not_called()
    assert creds.token
    assert creds.sandbox_id == "k8s-worker-soc-run-10"
    assert not connector.is_active("run-10")


@pytest.mark.unit
def test_k8s_sandbox_credentials_only_does_not_load_batch_api():
    connector = K8sSandboxConnector(settings=_settings_stub(k8s_sandbox_credentials_only=True))
    assert connector._batch_api is None


@pytest.mark.unit
def test_k8s_sandbox_credentials_only_constructor_override_wins_over_settings():
    connector = K8sSandboxConnector(
        settings=_settings_stub(k8s_sandbox_credentials_only=False),
        credentials_only=True,
    )
    assert connector._batch_api is None
    creds = connector.create("run-11", "soc")
    assert creds.token
