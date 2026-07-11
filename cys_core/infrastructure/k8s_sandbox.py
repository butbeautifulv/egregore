from __future__ import annotations

import uuid
from typing import Any

from bootstrap.settings import Settings, get_settings
from cys_core.domain.workers.models import SandboxCredentials
from cys_core.infrastructure.sandbox import LocalSandboxConnector


class K8sSandboxConnector:
    """Kubernetes Job-backed worker sandbox with local fallback when API is unavailable."""

    name = "k8s"

    def __init__(
        self,
        *,
        namespace: str | None = None,
        batch_api: Any = None,
        fallback: LocalSandboxConnector | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self.namespace = namespace or self._settings.k8s_namespace
        self._batch_api = batch_api if batch_api is not None else self._load_batch_api()
        self._fallback = fallback or LocalSandboxConnector()
        self._job_names: dict[str, str] = {}

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
        if self._batch_api is None:
            raise RuntimeError("Kubernetes batch API client is not configured")
        job_name = self._job_name(run_id, persona)
        body = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": job_name,
                "namespace": self.namespace,
                "labels": {"app": "cys-agi-worker", "persona": persona, "run-id": run_id[:32]},
            },
            "spec": {
                "ttlSecondsAfterFinished": 300,
                "template": {
                    "metadata": {"labels": {"app": "cys-agi-worker", "persona": persona}},
                    "spec": {
                        "restartPolicy": "Never",
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

    def _delete_job(self, run_id: str) -> None:
        job_name = self._job_names.pop(run_id, None)
        if job_name is None or self._batch_api is None:
            return
        self._batch_api.delete_namespaced_job(
            name=job_name,
            namespace=self.namespace,
            propagation_policy="Background",
        )

    def create(self, run_id: str, persona: str, policy: str = "default") -> SandboxCredentials:
        try:
            job_name = self._create_job(run_id, persona, policy)
            return SandboxCredentials(
                sandbox_id=f"k8s-{job_name}",
                endpoint=f"kubernetes://{self.namespace}/job/{job_name}",
                token=f"tok-{policy}-{uuid.uuid4().hex[:8]}",
            )
        except Exception:
            creds = self._fallback.create(run_id, persona, policy)
            return creds.model_copy(update={"sandbox_id": f"k8s-fallback-{creds.sandbox_id}"})

    def destroy(self, run_id: str) -> None:
        try:
            self._delete_job(run_id)
        except Exception:
            pass
        self._fallback.destroy(run_id)

    async def acreate(self, run_id: str, persona: str, policy: str = "default") -> SandboxCredentials:
        return self.create(run_id, persona, policy)

    async def adestroy(self, run_id: str) -> None:
        self.destroy(run_id)

    def is_active(self, run_id: str) -> bool:
        return run_id in self._job_names or self._fallback.is_active(run_id)
