from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog

from cys_core.domain.workers.models import RunResult, WorkerJob, WorkerJobStatus
from cys_core.infrastructure.execution.envelope import SubprocessJobEnvelope

logger = structlog.get_logger(__name__)

_TERMINAL_STATUSES = frozenset(
    {WorkerJobStatus.COMPLETED, WorkerJobStatus.FAILED, WorkerJobStatus.AWAITING_APPROVAL}
)


class K8sExecutionBackend:
    """Places one Kubernetes Job per job run, one job per pod (Phase 3.0/3.1
    fix — the Job this creates runs `run-sandboxed-job --job-json env:...`,
    not `worker.daemon`, so the pod actually executes *this* job instead of
    dequeuing whatever's next for the persona).

    Deliberately does not go through SandboxConnector.create() to place the
    pod (Discovery C, decision (b)) — it talks to the Batch API directly.
    RunWorkerJob.execute() running inside the pod still calls
    K8sSandboxConnector.create() for token minting, but with
    K8S_SANDBOX_CREDENTIALS_ONLY=true set in the pod's env (Discovery F), so
    it mints a token instead of creating a second Job.

    The result comes back via job_store polling, not stdout (Phase 3.4) —
    container stdout isn't as easy for a Dispatcher to read as a subprocess's
    is. job_store only carries status/error today (Discovery E/3.4 gap), so
    the reconstructed RunResult's `finding` is empty here; the actual finding
    content already reaches its system of record via the agent bus/
    engagement store the same way it does for every other backend, so this
    is a narrower gap than "the finding was lost" — just that this port's
    return value doesn't carry it for K8s the way it does for
    in_process/subprocess.
    """

    owns_timeout = True

    def __init__(
        self,
        *,
        job_store: Any,
        namespace: str,
        image: str,
        job_timeout_resolver: Any,
        batch_api: Any = None,
        poll_interval_s: float = 1.0,
        tool_gateway_url: str = "",
        runtime_class: str | None = None,
    ) -> None:
        """``job_timeout_resolver(job) -> float`` resolves the per-persona/
        per-phase job timeout (Settings.resolve_worker_job_timeout) — injected
        rather than computed here, since cys_core/infrastructure must not
        import bootstrap.settings directly (same hexagon-inversion rule as
        Discovery D's fix in budget_adapter.py); only the interfaces-layer
        caller has a Settings instance to build this closure from.

        ``runtime_class`` (Phase 4, e.g. "gvisor") requires the containerd
        shim + RuntimeClass CR already installed on the cluster (ops, not
        this repo) — when unset, no runtimeClassName field is added at all,
        i.e. today's runc behavior, unchanged.
        """
        self._job_store = job_store
        self.namespace = namespace
        self._image = image
        self._job_timeout_resolver = job_timeout_resolver
        self._batch_api = batch_api if batch_api is not None else self._load_batch_api()
        self._poll_interval_s = poll_interval_s
        self._tool_gateway_url = tool_gateway_url
        self._runtime_class = runtime_class

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

    def _build_job_body(
        self,
        *,
        job_name: str,
        run_id: str,
        persona: str,
        envelope_json: str,
        job_timeout: float,
    ) -> dict:
        env = [
            {"name": "RUN_ID", "value": run_id},
            {"name": "JOB_PAYLOAD_JSON", "value": envelope_json},
            {"name": "K8S_SANDBOX_CREDENTIALS_ONLY", "value": "true"},
        ]
        if self._tool_gateway_url:
            env.append({"name": "USE_TOOL_GATEWAY", "value": "true"})
            env.append({"name": "TOOL_GATEWAY_URL", "value": self._tool_gateway_url})
        pod_spec: dict[str, Any] = {"restartPolicy": "Never"}
        if self._runtime_class:
            pod_spec["runtimeClassName"] = self._runtime_class
        return {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": job_name,
                "namespace": self.namespace,
                "labels": {"app": "egregore-worker", "persona": persona, "run-id": run_id[:32]},
            },
            "spec": {
                "ttlSecondsAfterFinished": 300,
                "activeDeadlineSeconds": int(job_timeout) + 30,
                "backoffLimit": 0,
                "template": {
                    "metadata": {"labels": {"app": "egregore-worker", "persona": persona}},
                    "spec": {
                        **pod_spec,
                        "containers": [
                            {
                                "name": "worker",
                                "image": self._image,
                                # "uv run egregore ..." not bare "egregore" — the worker
                                # image doesn't export the venv's bin/ onto PATH (see
                                # deploy/Dockerfile's own CMD), only `uv run` resolves it.
                                "args": [
                                    "uv",
                                    "run",
                                    "egregore",
                                    "run-sandboxed-job",
                                    "--job-json",
                                    "env:JOB_PAYLOAD_JSON",
                                ],
                                "env": env,
                                "securityContext": {
                                    "runAsNonRoot": True,
                                    "readOnlyRootFilesystem": True,
                                    "allowPrivilegeEscalation": False,
                                },
                            }
                        ],
                    },
                },
            },
        }

    def _run_sync(
        self, job: WorkerJob, budgeted: WorkerJob, session_id: str, job_timeout: float
    ) -> RunResult:
        if self._batch_api is None:
            raise RuntimeError(
                "kubernetes execution backend unavailable — batch API client is not "
                "configured; refusing to run the agent unsandboxed"
            )
        run_id = job.job_id
        job_name = self._job_name(run_id, job.persona)
        envelope = SubprocessJobEnvelope(job=job, budgeted=budgeted, session_id=session_id)
        body = self._build_job_body(
            job_name=job_name,
            run_id=run_id,
            persona=job.persona,
            envelope_json=envelope.model_dump_json(),
            job_timeout=job_timeout,
        )
        self._batch_api.create_namespaced_job(namespace=self.namespace, body=body)
        try:
            return self._poll_for_result(job, job_timeout=job_timeout)
        finally:
            try:
                self._batch_api.delete_namespaced_job(
                    name=job_name, namespace=self.namespace, propagation_policy="Background"
                )
            except Exception:
                logger.error(
                    "k8s_execution_backend_job_delete_failed",
                    run_id=run_id,
                    job_name=job_name,
                    namespace=self.namespace,
                    exc_info=True,
                )

    def _poll_for_result(self, job: WorkerJob, *, job_timeout: float) -> RunResult:
        deadline = time.monotonic() + job_timeout
        while True:
            record = self._job_store.get(job.job_id)
            if record is not None and record.status in _TERMINAL_STATUSES:
                return RunResult(
                    job_id=job.job_id,
                    persona=job.persona,
                    success=record.status == WorkerJobStatus.COMPLETED,
                    error=record.last_error or record.failure_reason,
                )
            if time.monotonic() >= deadline:
                raise TimeoutError(f"kubernetes job for job_id={job.job_id!r} did not complete in time")
            time.sleep(self._poll_interval_s)

    async def execute(
        self,
        job: WorkerJob,
        budgeted: WorkerJob,
        session_id: str,
        job_state: dict[str, str],
    ) -> RunResult:
        job_timeout = self._job_timeout_resolver(job)
        return await asyncio.to_thread(self._run_sync, job, budgeted, session_id, job_timeout)
