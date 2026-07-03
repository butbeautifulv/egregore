from __future__ import annotations

import asyncio

import structlog

from bootstrap.container import get_container
from cys_core.infrastructure.daemon_runner import run_poll_daemon
from cys_core.observability.langfuse_client import flush_langfuse
from cys_core.observability.logging_setup import configure_logging
from cys_core.observability.otel import setup_otel
from interfaces.worker.orchestrator import WorkerOrchestrator

logger = structlog.get_logger(__name__)


class WorkerDaemon:
    """Long-running worker that consumes persona-scoped jobs until stopped or idle."""

    def __init__(
        self,
        persona: str,
        *,
        max_jobs: int | None = None,
        idle_timeout: float = 0.0,
    ) -> None:
        self.persona = persona
        self.max_jobs = max_jobs
        self.idle_timeout = idle_timeout
        self._stop = False

    def request_stop(self) -> None:
        self._stop = True

    async def run(self) -> int:
        configure_logging("egregore-worker")
        setup_otel(service_name="egregore-worker")
        logger.info("worker daemon starting", persona=self.persona)
        orch = WorkerOrchestrator(persona=self.persona)
        processed = 0

        async def process_one(_timeout: float) -> bool:
            nonlocal processed
            if self.max_jobs is not None and processed >= self.max_jobs:
                self.request_stop()
                return False
            result = await orch.process_next()
            if result is None:
                return False
            processed += 1
            flush_langfuse()
            get_container().get_trace_backend().flush()
            return True

        await run_poll_daemon(
            process_one,
            idle_timeout=self.idle_timeout,
            idle_sleep=asyncio.sleep,
            request_stop=self.request_stop,
        )
        return processed


def run_worker_daemon(
    persona: str,
    *,
    max_jobs: int | None = None,
    idle_timeout: float = 0.0,
) -> int:
    return asyncio.run(WorkerDaemon(persona, max_jobs=max_jobs, idle_timeout=idle_timeout).run())


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Worker job consumer daemon")
    parser.add_argument("--persona", required=True)
    parser.add_argument("--max-jobs", type=int, default=0)
    parser.add_argument("--idle-timeout", type=float, default=0.0)
    args = parser.parse_args()
    processed = run_worker_daemon(
        args.persona,
        max_jobs=args.max_jobs if args.max_jobs > 0 else None,
        idle_timeout=args.idle_timeout,
    )
    raise SystemExit(0 if processed >= 0 else 1)
