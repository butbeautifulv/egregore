from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog

from bootstrap.settings import Settings, get_settings
from cys_core.domain.security.sandbox_tokens import mint_sandbox_token
from cys_core.domain.workers.models import SandboxCredentials

logger = structlog.get_logger(__name__)


class K8sSandboxConnector:
    """Kubernetes Job-backed worker sandbox — one Job per job run, no unsandboxed fallback.

    Lifecycle contract mirrors DockerSandboxConnector /
    ``cys_core.infrastructure.tools.adapters.docker_sandbox``: if the Kubernetes API is
    unreachable, misconfigured, or the Job's pod never becomes ready, ``create()`` /
    ``acreate()`` raise instead of silently handing back credentials for a sandbox that
    doesn't exist. A pentest-agent platform that silently falls back to unsandboxed
    execution when the sandbox is unavailable defeats the entire point of having one —
    this connector used to do exactly that (fall back to ``LocalSandboxConnector`` on
    *any* exception), which was the original bug.

    Historical gap (backlog Q2-1): the agent's LLM/tool loop used to always execute in
    the calling worker process, never inside the Job's pod this class creates — the pod
    ran an unrelated queue-draining ``worker.daemon`` (Discovery A/Phase 3.0 in
    docs/MICROSERVICES_SPLIT_PHASES_DETAIL.md). That's now solved for jobs dispatched via
    ``K8sExecutionBackend`` (``cys_core.infrastructure.execution.k8s_backend``), which
    places the pod directly through the Batch API (not through this class's ``create()``)
    running ``run-sandboxed-job`` for that *specific* job. This class's own ``create()``/
    ``_create_job`` below is unchanged and still creates its own Job when called directly
    (``credentials_only=False``, the default) — that path is only actually exercised
    today for token-minting on the in_process/subprocess backends, where the agent loop
    runs in the calling process regardless, per the sandbox_tokens gap in §11 of
    docs/MICROSERVICES_SPLIT_PLAN.md. When ``credentials_only=True`` (set by
    ``K8sExecutionBackend`` in the pod's own env), ``create()``/``acreate()`` skip Job
    creation and just mint a token instead — the pod calling this already *is* the Job
    that backend placed for this run_id; creating another one would be a second,
    parasitic Job the same-run_id guard below can't catch, since it's a fresh process
    with an empty ``_job_names`` (Discovery F).
    """

    name = "k8s"

    def __init__(
        self,
        *,
        namespace: str | None = None,
        batch_api: Any = None,
        settings: Settings | None = None,
        ttl_seconds: float | None = None,
        ready_timeout_s: float | None = None,
        ready_poll_interval_s: float | None = None,
        credentials_only: bool | None = None,
        runtime_class: str | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self.namespace = namespace or self._settings.k8s_namespace
        self._runtime_class = (
            runtime_class if runtime_class is not None else self._settings.k8s_runtime_class
        )
        self._credentials_only = (
            credentials_only if credentials_only is not None else self._settings.k8s_sandbox_credentials_only
        )
        # In credentials_only mode (set by K8sExecutionBackend in the pod's own
        # env — Discovery F) this connector never creates/waits/deletes a Job,
        # so it has no need for a Batch API client at all; skip loading one
        # (avoids requiring kube-apiserver RBAC access from inside the pod
        # just to mint a token for the Job that's already running it).
        self._batch_api: Any = (
            None
            if self._credentials_only
            else (batch_api if batch_api is not None else self._load_batch_api())
        )
        self._job_names: dict[str, str] = {}
        self._ttl_seconds = (
            ttl_seconds if ttl_seconds is not None else self._settings.k8s_sandbox_ttl_seconds
        )
        self._ready_timeout_s = (
            ready_timeout_s
            if ready_timeout_s is not None
            else self._settings.k8s_sandbox_ready_timeout_s
        )
        self._ready_poll_interval_s = (
            ready_poll_interval_s
            if ready_poll_interval_s is not None
            else self._settings.k8s_sandbox_ready_poll_interval_s
        )

    def _load_batch_api(self) -> Any:
        try:
            import importlib

            k8s = importlib.import_module("kubernetes")
            client = k8s.client
            config = k8s.config

            try:
                config.load_incluster_config()
            except config.ConfigException:
                config.load_kube_config()
            return client.BatchV1Api()
        except Exception:
            return None

    def _job_name(self, run_id: str, persona: str) -> str:
        raw = f"worker-{persona}-{run_id}".lower().replace("_", "-")
        return raw[:63].rstrip("-")

    def _create_job(self, run_id: str, persona: str, policy: str) -> str:
        job_name = self._job_name(run_id, persona)
        pod_spec: dict[str, Any] = {"restartPolicy": "Never"}
        if self._runtime_class:
            pod_spec["runtimeClassName"] = self._runtime_class
        body = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": job_name,
                "namespace": self.namespace,
                "labels": {"app": "cys-agi-worker", "persona": persona, "run-id": run_id[:32]},
            },
            "spec": {
                # Cleanup after the Job finishes (success or failure) so completed Jobs
                # don't accumulate.
                "ttlSecondsAfterFinished": 300,
                # Hard wall-clock cap: kubelet/job-controller force-kill the pod if the
                # agent hangs, even if nothing on the Python side ever calls destroy().
                "activeDeadlineSeconds": int(self._ttl_seconds),
                # One-shot job — never retry a failed attempt with a fresh pod under the
                # same Job (that would look like "state reuse" from the caller's point of
                # view). A new job run always gets create()'d fresh with a new run_id.
                "backoffLimit": 0,
                "template": {
                    "metadata": {"labels": {"app": "cys-agi-worker", "persona": persona}},
                    "spec": {
                        **pod_spec,
                        "containers": [
                            {
                                "name": "worker",
                                "image": self._settings.k8s_worker_image,
                                "args": [
                                    "python",
                                    "-m",
                                    "interfaces.worker.daemon",
                                    "--persona",
                                    persona,
                                    "--max-jobs",
                                    "1",
                                ],
                                "env": [{"name": "RUN_ID", "value": run_id}],
                            }
                        ],
                    },
                },
            },
        }
        self._batch_api.create_namespaced_job(namespace=self.namespace, body=body)
        self._job_names[run_id] = job_name
        return job_name

    def _wait_job_ready(self, job_name: str) -> None:
        """Poll Job status until its pod is admitted/running; fail closed on timeout/failure.

        Deliberately reads Job status only (no CoreV1Api pod lookup) — this class's only
        Kubernetes dependency is BatchV1Api, and ``status.active`` / ``status.ready`` /
        ``status.failed`` are enough to tell whether a pod actually started, which is the
        thing the original bug never checked at all.
        """
        deadline = time.monotonic() + self._ready_timeout_s
        while True:
            job = self._batch_api.read_namespaced_job(name=job_name, namespace=self.namespace)
            status = getattr(job, "status", None)
            failed = int(getattr(status, "failed", 0) or 0)
            if failed:
                raise RuntimeError(f"kubernetes job {job_name} failed before becoming ready")
            active = int(getattr(status, "active", 0) or 0)
            ready = int(getattr(status, "ready", 0) or 0)
            succeeded = int(getattr(status, "succeeded", 0) or 0)
            if active >= 1 or ready >= 1 or succeeded >= 1:
                return
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"kubernetes job {job_name} did not become ready within "
                    f"{self._ready_timeout_s}s"
                )
            time.sleep(self._ready_poll_interval_s)

    def _delete_job(self, job_name: str) -> None:
        self._batch_api.delete_namespaced_job(
            name=job_name,
            namespace=self.namespace,
            propagation_policy="Background",
        )

    def create(
        self,
        run_id: str,
        persona: str,
        policy: str = "default",
        *,
        tenant_id: str = "default",
    ) -> SandboxCredentials:
        if self._credentials_only:
            # The pod running this code is the Job K8sExecutionBackend already
            # created for this exact run_id (Discovery F) — creating another
            # one here would be a second, parasitic Job that the same-run_id
            # guard below can't catch (fresh process, empty _job_names). Just
            # mint the token; there is nothing to place.
            token = mint_sandbox_token(
                run_id=run_id,
                persona=persona,
                tenant_id=tenant_id,
                job_id=run_id,
                ttl_s=self._ttl_seconds,
                secret=self._settings.bus_signing_key_bytes,
            )
            return SandboxCredentials(
                sandbox_id=f"k8s-{self._job_name(run_id, persona)}",
                endpoint=f"kubernetes://{self.namespace}/job/{self._job_name(run_id, persona)}",
                token=token,
            )
        if self._batch_api is None:
            raise RuntimeError(
                "kubernetes sandbox unavailable — batch API client is not configured; "
                "refusing to run the agent unsandboxed"
            )
        if run_id in self._job_names:
            # A fresh Job must exist per job run — never hand out credentials for a
            # run_id that already has an active sandbox tracked (no state reuse across
            # jobs). Callers must destroy() before create()-ing again for the same id.
            raise RuntimeError(
                f"sandbox already active for run_id={run_id!r}; refusing to reuse state"
            )

        job_name = self._create_job(run_id, persona, policy)
        try:
            self._wait_job_ready(job_name)
        except Exception:
            logger.error(
                "k8s_sandbox_job_not_ready",
                run_id=run_id,
                job_name=job_name,
                namespace=self.namespace,
                exc_info=True,
            )
            self._job_names.pop(run_id, None)
            try:
                self._delete_job(job_name)
            except Exception:
                logger.error(
                    "k8s_sandbox_cleanup_after_failed_create_error",
                    run_id=run_id,
                    job_name=job_name,
                    namespace=self.namespace,
                    exc_info=True,
                )
            raise

        token = mint_sandbox_token(
            run_id=run_id,
            persona=persona,
            tenant_id=tenant_id,
            job_id=run_id,
            ttl_s=self._ttl_seconds,
            secret=self._settings.bus_signing_key_bytes,
        )
        return SandboxCredentials(
            sandbox_id=f"k8s-{job_name}",
            endpoint=f"kubernetes://{self.namespace}/job/{job_name}",
            token=token,
        )

    def destroy(self, run_id: str) -> None:
        job_name = self._job_names.pop(run_id, None)
        if job_name is None or self._batch_api is None:
            return
        try:
            self._delete_job(job_name)
        except Exception:
            # Previously a silent `pass` here (FIXME): a failed Job deletion left an
            # orphaned pod running with zero signal — invisible resource/credential leak,
            # and it violated the "fresh sandbox per job" guarantee for anyone reusing the
            # run_id. Log it loudly. We don't re-raise: destroy() runs from a `finally`
            # block in RunWorkerJob.execute() and must not mask the job's real
            # success/failure outcome; activeDeadlineSeconds/ttlSecondsAfterFinished on
            # the Job spec bound the leak even when this delete call itself fails.
            logger.error(
                "k8s_sandbox_job_delete_failed",
                run_id=run_id,
                job_name=job_name,
                namespace=self.namespace,
                exc_info=True,
            )

    async def acreate(
        self,
        run_id: str,
        persona: str,
        policy: str = "default",
        *,
        tenant_id: str = "default",
    ) -> SandboxCredentials:
        # create() does blocking network calls (k8s API) and a blocking poll loop in
        # _wait_job_ready — run it off the event loop, same pattern used elsewhere in
        # this codebase for sync I/O inside async def (see job_finalizer.py, queue.py).
        return await asyncio.to_thread(self.create, run_id, persona, policy, tenant_id=tenant_id)

    async def adestroy(self, run_id: str) -> None:
        await asyncio.to_thread(self.destroy, run_id)

    def is_active(self, run_id: str) -> bool:
        return run_id in self._job_names
