from __future__ import annotations

import asyncio
import json
import sys

import structlog

from cys_core.domain.workers.models import RunResult, WorkerJob
from cys_core.infrastructure.execution.envelope import SubprocessJobEnvelope

logger = structlog.get_logger(__name__)


class SubprocessExecutionBackend:
    """Runs a job's execute() call in a child `run-sandboxed-job` process.

    The child owns its own soft-timeout and salvage (Phase 2.2a/2.2b in
    docs/MICROSERVICES_SPLIT_PHASES_DETAIL.md) — this backend just spawns it,
    feeds it an envelope over stdin, and waits for one final RunResult JSON
    line on stdout. ``owns_timeout = True`` tells WorkerOrchestrator.run_job
    to wrap this call in a hard job_timeout dead-man's switch instead of
    racing its own soft-timeout against the child's (see Phase 2.0) — when
    that outer wait_for cancels this coroutine, `finally` below kills the
    child (Phase 2.3).

    Invoked as `sys.executable -m interfaces.cli.main` rather than shelling
    out to the `egregore` console script, so it doesn't depend on the venv's
    bin/ directory being on PATH — only on running the same interpreter.
    """

    owns_timeout = True

    def __init__(self, *, python_executable: str | None = None, command: list[str] | None = None) -> None:
        """``command``, if given, replaces the default argv entirely — used by
        tests to point at a lightweight stand-in child instead of spawning the
        real CLI (which needs a live Postgres-backed container)."""
        self._python_executable = python_executable or sys.executable
        self._command = command

    async def execute(
        self,
        job: WorkerJob,
        budgeted: WorkerJob,
        session_id: str,
        job_state: dict[str, str],
    ) -> RunResult:
        envelope = SubprocessJobEnvelope(job=job, budgeted=budgeted, session_id=session_id)
        argv = self._command or [
            self._python_executable,
            "-m",
            "interfaces.cli.main",
            "run-sandboxed-job",
            "--job-json",
            "-",
        ]
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await proc.communicate(envelope.model_dump_json().encode())
        finally:
            if proc.returncode is None:
                logger.warning(
                    "subprocess_execution_backend killing unfinished child",
                    job_id=job.job_id,
                    persona=job.persona,
                )
                proc.kill()
                await proc.wait()

        if proc.returncode not in (0, 1):
            logger.error(
                "subprocess_execution_backend child exited abnormally",
                job_id=job.job_id,
                persona=job.persona,
                returncode=proc.returncode,
                stderr=stderr.decode(errors="replace")[-4000:],
            )
            return RunResult(
                job_id=job.job_id,
                persona=job.persona,
                success=False,
                error=f"run_sandboxed_job_exit_{proc.returncode}",
            )

        try:
            # Only the last non-empty stdout line is the RunResult contract
            # (interfaces.cli.main.cmd_run_sandboxed_job prints it last,
            # compact, single-line) — anything a dependency prints to stdout
            # ahead of it (e.g. litellm's own error banners, which bypass
            # structlog entirely) lands on earlier lines and must not break
            # the parse.
            lines = [line for line in stdout.decode().splitlines() if line.strip()]
            parsed = json.loads(lines[-1])
            return RunResult.model_validate(parsed["result"])
        except (json.JSONDecodeError, KeyError, ValueError, IndexError) as exc:
            logger.error(
                "subprocess_execution_backend could not parse child output",
                job_id=job.job_id,
                persona=job.persona,
                error=str(exc),
                stderr=stderr.decode(errors="replace")[-4000:],
            )
            return RunResult(
                job_id=job.job_id,
                persona=job.persona,
                success=False,
                error="run_sandboxed_job_unparseable_output",
            )
