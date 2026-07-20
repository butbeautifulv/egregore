from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from bootstrap.container import get_container
from bootstrap.settings import settings
from cys_core.observability.logging_setup import configure_logging
from cys_core.observability.otel import setup_otel
from cys_core.observability.prometheus_setup import register_multiprocess_shutdown
from cys_core.registry.agents import get_agent_registry


def cmd_worker(args: argparse.Namespace) -> int:
    get_container()
    configure_logging("egregore-worker")
    setup_otel(service_name="egregore-worker")
    if getattr(args, "metrics_port", None) is not None:
        os.environ["EGREGORE_METRICS_PORT"] = str(args.metrics_port)
    idle_timeout = settings.worker_idle_timeout if args.idle_timeout is None else args.idle_timeout
    if args.daemon:
        from interfaces.worker.daemon import run_worker_daemon

        processed = run_worker_daemon(
            args.persona,
            max_jobs=args.max_jobs,
            idle_timeout=idle_timeout,
        )
        get_container().get_trace_backend().flush()
        print(json.dumps({"persona": args.persona, "processed": processed}, indent=2))
        return 0

    async def _run() -> dict:
        orch = get_container().get_worker_orchestrator(persona=args.persona or None)
        if args.once:
            result = await orch.process_next()
            return {"result": result.model_dump() if result else None}
        results = []
        for _ in range(args.max_jobs or 1):
            result = await orch.process_next()
            if result is None:
                break
            results.append(result.model_dump())
        return {"processed": len(results), "results": results}

    out = asyncio.run(_run())
    get_container().get_trace_backend().flush()
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def cmd_run_sandboxed_job(args: argparse.Namespace) -> int:
    """Execute one already-budgeted WorkerJob directly — child-process
    entrypoint for SubprocessExecutionBackend (and, later, K8s/Docker
    backends). The Dispatcher (WorkerOrchestrator.run_job, running in the
    parent) already popped this job off the queue, resolved dependency
    deferral, and enriched its budget — this command must not repeat any of
    that (would race/duplicate against the shared queue).

    What it *does* own, locally, in this process: soft-timeout + salvage
    (Discovery A) and JobBudgetTracker/configure_job_cost configuration
    (Discovery D) — both are process-local state that does not survive the
    parent/child boundary, so the child must set them up and tear them down
    itself rather than trusting whatever the parent configured for its own,
    separate process. See docs/MICROSERVICES_SPLIT_PHASES_DETAIL.md Phase
    2.2a/2.2b. Not for interactive use.
    """
    get_container()
    configure_logging("egregore-worker-sandboxed", stream=sys.stderr)
    setup_otel(service_name="egregore-worker-sandboxed")
    from cys_core.infrastructure.execution.envelope import SubprocessJobEnvelope
    from cys_core.infrastructure.execution.sandboxed_entrypoint import execute_sandboxed_job

    if args.job_json == "-":
        raw = sys.stdin.read()
    elif args.job_json.startswith("env:"):
        # K8s/Docker pods can't be piped stdin after creation (Discovery E) —
        # K8sExecutionBackend/DockerExecutionBackend pass the envelope as an
        # env var instead and point --job-json at its name.
        env_var = args.job_json.removeprefix("env:")
        raw = os.environ[env_var]
    else:
        raw = args.job_json
    envelope = SubprocessJobEnvelope.model_validate_json(raw)
    job = envelope.job

    async def _run() -> dict:
        container = get_container()
        job_timeout = container.settings.resolve_worker_job_timeout(
            persona=job.persona,
            phase=str(job.payload.get("phase") or ""),
        )
        result = await execute_sandboxed_job(
            envelope,
            run_worker_job=container.get_run_worker_job(persona=job.persona),
            metrics=container.get_metrics_port(),
            tool_chain_policy=container.get_tool_chain_policy(),
            job_timeout=job_timeout,
            soft_timeout=job_timeout * container.settings.worker_soft_timeout_fraction,
            default_cost_rate=container.settings.job_cost_per_1k_tokens_usd,
        )
        return {"result": result.model_dump()}

    out = asyncio.run(_run())
    get_container().get_trace_backend().flush()
    # Compact, single-line — SubprocessExecutionBackend parses only the last
    # stdout line as the RunResult (see subprocess_backend.py); anything
    # else the process tree prints to stdout (litellm banners, stray
    # warnings) lands on earlier lines and is ignored rather than corrupting
    # the parse.
    print(json.dumps(out, ensure_ascii=False))
    return 0 if out["result"]["success"] else 1


def cmd_tool_gateway(args: argparse.Namespace) -> int:
    from interfaces.gateways.tool.server import serve_forever

    get_container()
    configure_logging("egregore-tool-gateway")
    setup_otel(service_name="egregore-tool-gateway")
    host = args.host or settings.tool_gateway_bind_host
    port = args.port or settings.tool_gateway_bind_port
    print(json.dumps({"service": "tool-gateway", "host": host, "port": port}, indent=2))
    asyncio.run(serve_forever(host, port))
    return 0


def cmd_critic(args: argparse.Namespace) -> int:
    from interfaces.control_plane.critic_daemon import run_critic_daemon

    processed = run_critic_daemon(idle_timeout=args.idle_timeout)
    print(json.dumps({"service": "critic", "processed": processed}, indent=2, ensure_ascii=False))
    return 0


def cmd_coordinator(args: argparse.Namespace) -> int:
    from interfaces.control_plane.coordinator_daemon import run_coordinator_daemon

    processed = run_coordinator_daemon(idle_timeout=args.idle_timeout)
    print(json.dumps({"service": "coordinator", "processed": processed}, indent=2, ensure_ascii=False))
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    from interfaces.control_plane.status_store import get_status_store

    print(json.dumps(get_status_store().snapshot(), indent=2, ensure_ascii=False))
    return 0


def cmd_agent(args: argparse.Namespace) -> int:
    """Not functional in backend/dispatcher — cys_core.runtime.agent lives in
    backend/agent-runtime now (docs/MICROSERVICES_SPLIT_PLAN.md §1). Kept for CLI
    parser/arg-parity; run this subcommand against agent-runtime's own CLI instead."""
    from cys_core.runtime.agent import get_runtime  # ty: ignore[unresolved-import]

    configure_logging("egregore-agent")
    setup_otel(service_name="egregore-agent")
    registry = get_agent_registry()
    runtime = get_runtime()
    if args.name not in registry.names():
        print(f"Unknown agent: {args.name}. Choose from: {', '.join(registry.names())}", file=sys.stderr)
        return 1
    defn = registry.get(args.name)
    user_input = args.input or defn.sample_input or ""
    result = runtime.run(args.name, user_input, session_id=f"agent-{args.name}")
    get_container().get_trace_backend().flush()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Egregore worker/control-plane processes")
    sub = parser.add_subparsers(dest="command", required=True)

    registry = get_agent_registry()
    worker_names = [n for n in registry.names() if registry.get(n).role in ("worker", "specialist")]

    worker = sub.add_parser("worker", help="Process queued worker jobs")
    worker.add_argument("--once", action="store_true", help="Process single job")
    worker.add_argument("--max-jobs", type=int, default=None, help="Max jobs (daemon: unlimited by default; batch: 1)")
    worker.add_argument("--persona", default="", help="Worker persona (required for daemon/Kafka)")
    worker.add_argument("--daemon", action="store_true", help="Run as long-lived daemon")
    worker.add_argument(
        "--idle-timeout",
        type=float,
        default=None,
        help="Exit after N seconds idle (daemon). Default: WORKER_IDLE_TIMEOUT (0=forever)",
    )
    worker.add_argument(
        "--metrics-port",
        type=int,
        default=None,
        help="Expose Prometheus /metrics on this port (daemon). Default: EGREGORE_METRICS_PORT env",
    )
    worker.set_defaults(func=cmd_worker)

    run_sandboxed = sub.add_parser(
        "run-sandboxed-job",
        help="Execute one budgeted job envelope directly (child-process entrypoint, not for interactive use)",
    )
    run_sandboxed.add_argument(
        "--job-json",
        default="-",
        help="SubprocessJobEnvelope as JSON, '-' to read from stdin (default), "
        "or 'env:VAR_NAME' to read from that env var (K8s/Docker backends)",
    )
    run_sandboxed.set_defaults(func=cmd_run_sandboxed_job)

    tool_gateway = sub.add_parser("tool-gateway", help="Run the MCP Tool Gateway (PEP for sandboxed tool calls)")
    tool_gateway.add_argument("--host", default=None, help="Bind host. Default: TOOL_GATEWAY_BIND_HOST")
    tool_gateway.add_argument("--port", type=int, default=None, help="Bind port. Default: TOOL_GATEWAY_BIND_PORT")
    tool_gateway.set_defaults(func=cmd_tool_gateway)

    critic = sub.add_parser("critic", help="Run critic bus consumer daemon")
    critic.add_argument("--idle-timeout", type=float, default=0.0, help="Exit after N seconds idle (0=run forever)")
    critic.set_defaults(func=cmd_critic)

    coordinator = sub.add_parser("coordinator", help="Run coordinator bus consumer daemon")
    coordinator.add_argument(
        "--idle-timeout", type=float, default=0.0, help="Exit after N seconds idle (0=run forever)"
    )
    coordinator.set_defaults(func=cmd_coordinator)

    status = sub.add_parser("status", help="Show control plane status snapshot")
    status.set_defaults(func=cmd_status)

    agent = sub.add_parser("agent", help="Run a single worker agent (debug)")
    agent.add_argument("name", choices=worker_names)
    agent.add_argument("--input", "-i", default=None)
    agent.set_defaults(func=cmd_agent)

    return parser


def main() -> None:
    register_multiprocess_shutdown()
    get_container()
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
