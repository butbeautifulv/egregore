from __future__ import annotations

import argparse
import asyncio
import json
import sys

from config import settings
from cys_core.registry.agents import get_agent_registry
from cys_core.runtime.agent import get_runtime


def cmd_ingest(args: argparse.Namespace) -> int:
    from ingress.router import get_event_ingress

    ingress = get_event_ingress()
    payload = json.loads(args.payload) if args.payload.startswith("{") else {"raw": args.payload}
    event, decision, job_ids = ingress.ingest(
        args.type,
        payload,
        severity=args.severity,
        source=args.source,
        event_id=args.event_id,
    )
    print(
        json.dumps(
            {
                "event": event.model_dump(),
                "routing": decision.model_dump(),
                "job_ids": job_ids,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def cmd_worker(args: argparse.Namespace) -> int:
    from workers.orchestrator import WorkerOrchestrator

    async def _run() -> dict:
        orch = WorkerOrchestrator()
        if args.once:
            result = await orch.process_next()
            return {"result": result.model_dump() if result else None}
        results = []
        for _ in range(args.max_jobs):
            result = await orch.process_next()
            if result is None:
                break
            results.append(result.model_dump())
        return {"processed": len(results), "results": results}

    out = asyncio.run(_run())
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    from control.status_store import get_status_store

    print(json.dumps(get_status_store().snapshot(), indent=2, ensure_ascii=False))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from ingress.api import create_app

    uvicorn.run(create_app(), host=args.host, port=args.port)
    return 0


def cmd_session(args: argparse.Namespace) -> int:
    from ingress.router import get_event_ingress

    ingress = get_event_ingress()
    event, decision, job_ids = ingress.ingest(
        "manual.investigation",
        {"goal": args.goal},
        severity="medium",
        source="user",
    )
    print(
        json.dumps(
            {
                "event": event.model_dump(),
                "routing": decision.model_dump(),
                "job_ids": job_ids,
                "message": "Investigation jobs enqueued. Run: python main.py worker --max-jobs N",
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def cmd_agent(args: argparse.Namespace) -> int:
    registry = get_agent_registry()
    runtime = get_runtime()
    if args.name not in registry.names():
        print(f"Unknown agent: {args.name}. Choose from: {', '.join(registry.names())}", file=sys.stderr)
        return 1
    defn = registry.get(args.name)
    user_input = args.input or defn.sample_input or ""
    result = runtime.run(args.name, user_input, session_id=f"agent-{args.name}")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def cmd_daemon(args: argparse.Namespace) -> int:
    from workers.daemon import run_daemon

    count = asyncio.run(
        run_daemon(
            persona=args.persona or None,
            max_jobs=args.max_jobs,
            idle_timeout=args.idle_timeout,
        )
    )
    print(json.dumps({"jobs_processed": count}))
    return 0


def cmd_adversarial_test(_args: argparse.Namespace) -> int:
    import pytest

    return pytest.main(["-q", "tests"])


def cmd_info(_args: argparse.Namespace) -> int:
    registry = get_agent_registry()
    print(
        json.dumps(
            {
                "project": "cys-agi",
                "stage": settings.stage,
                "mode": "event-driven",
                "llm_provider": settings.llm_provider,
                "llm_model": settings.llm_model,
                "workers": [a.name for a in registry.by_workers()],
                "control": [a.name for a in registry.by_control()],
                "agents": registry.names(),
                "postgres_url": settings.postgres_url,
                "redis_url": settings.redis_url,
                "use_memory_fallback": settings.use_memory_fallback,
                "use_kafka": settings.use_kafka,
                "agents_root": settings.agents_root,
            },
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CYS-AGI event-driven multi-agent platform")
    sub = parser.add_subparsers(dest="command", required=True)

    registry = get_agent_registry()
    worker_names = [n for n in registry.names() if registry.get(n).role in ("worker", "specialist")]

    ingest = sub.add_parser("ingest", help="Ingest structured security event and enqueue worker jobs")
    ingest.add_argument("--type", "-t", required=True, help="Event type (e.g. siem.alert)")
    ingest.add_argument("--payload", "-p", required=True, help="JSON payload or raw text")
    ingest.add_argument("--severity", "-s", default="medium")
    ingest.add_argument("--source", default="")
    ingest.add_argument("--event-id", default=None)
    ingest.set_defaults(func=cmd_ingest)

    worker = sub.add_parser("worker", help="Process queued worker jobs")
    worker.add_argument("--once", action="store_true", help="Process single job")
    worker.add_argument("--max-jobs", type=int, default=1, help="Max jobs per invocation")
    worker.set_defaults(func=cmd_worker)

    daemon = sub.add_parser("daemon", help="Run worker daemon (long-running, graceful SIGTERM)")
    daemon.add_argument("--persona", choices=worker_names, default=None, help="Persona to process (default: all)")
    daemon.add_argument("--max-jobs", type=int, default=0, help="Max jobs to process (0 = unlimited)")
    daemon.add_argument("--idle-timeout", type=float, default=0.0, help="Stop after N seconds idle (0 = run forever)")
    daemon.set_defaults(func=cmd_daemon)

    status = sub.add_parser("status", help="Show control plane status snapshot")
    status.set_defaults(func=cmd_status)

    serve = sub.add_parser("serve", help="Start FastAPI event/status server")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8080)
    serve.set_defaults(func=cmd_serve)

    session = sub.add_parser("session", help="Manual investigation — enqueue all workers")
    session.add_argument("--goal", "-g", required=True, help="Investigation goal")
    session.set_defaults(func=cmd_session)

    agent = sub.add_parser("agent", help="Run a single worker agent (debug)")
    agent.add_argument("name", choices=worker_names)
    agent.add_argument("--input", "-i", default=None)
    agent.set_defaults(func=cmd_agent)

    adv = sub.add_parser("adversarial-test", help="Run security test suite")
    adv.set_defaults(func=cmd_adversarial_test)

    info = sub.add_parser("info", help="Show configuration summary")
    info.set_defaults(func=cmd_info)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
