from __future__ import annotations

import asyncio
import signal

import structlog

from workers.orchestrator import WorkerOrchestrator

logger = structlog.get_logger(__name__)


class WorkerDaemon:
    """Long-running daemon consuming jobs for one or all personas."""

    def __init__(
        self,
        *,
        orchestrator: WorkerOrchestrator | None = None,
        persona: str | None = None,
        max_jobs: int = 0,
        idle_timeout: float = 0.0,
    ) -> None:
        self.orchestrator = orchestrator or WorkerOrchestrator()
        self.persona = persona
        self.max_jobs = max_jobs
        self.idle_timeout = idle_timeout
        self._stop_event = asyncio.Event()
        self._jobs_processed = 0

    def _setup_signals(self) -> None:
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._handle_stop_signal)

    def _handle_stop_signal(self) -> None:
        logger.info("daemon.shutdown_requested")
        self._stop_event.set()

    async def run(self) -> int:
        """Run daemon loop. Returns number of jobs processed."""
        self._setup_signals()
        idle_since: float | None = None

        logger.info(
            "daemon.started",
            persona=self.persona,
            max_jobs=self.max_jobs,
            idle_timeout=self.idle_timeout,
        )

        while not self._stop_event.is_set():
            result = await self.orchestrator.process_next()

            if result is None:
                if self.idle_timeout > 0:
                    if idle_since is None:
                        idle_since = asyncio.get_event_loop().time()
                    elif asyncio.get_event_loop().time() - idle_since >= self.idle_timeout:
                        logger.info("daemon.idle_timeout_reached", idle_timeout=self.idle_timeout)
                        break
                await asyncio.sleep(0.1)
                continue

            idle_since = None

            if self.persona and result.persona != self.persona:
                continue

            self._jobs_processed += 1
            if result.success:
                logger.info("daemon.job_completed", job_id=result.job_id, persona=result.persona)
            else:
                logger.warning("daemon.job_failed", job_id=result.job_id, error=result.error)

            if self.max_jobs > 0 and self._jobs_processed >= self.max_jobs:
                logger.info("daemon.max_jobs_reached", max_jobs=self.max_jobs)
                break

        logger.info("daemon.stopped", jobs_processed=self._jobs_processed)
        return self._jobs_processed


async def run_daemon(
    *,
    persona: str | None = None,
    max_jobs: int = 0,
    idle_timeout: float = 0.0,
    orchestrator: WorkerOrchestrator | None = None,
) -> int:
    """Convenience entry point for starting the daemon."""
    daemon = WorkerDaemon(
        orchestrator=orchestrator,
        persona=persona,
        max_jobs=max_jobs,
        idle_timeout=idle_timeout,
    )
    return await daemon.run()
