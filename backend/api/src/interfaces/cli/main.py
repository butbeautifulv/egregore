from __future__ import annotations

import argparse
import asyncio
import json
import sys

from bootstrap.container import get_container
from bootstrap.settings import settings
from cys_core.observability.prometheus_setup import register_multiprocess_shutdown
from cys_core.registry.agents import get_agent_registry


def cmd_ingest(args: argparse.Namespace) -> int:
    from interfaces.ingress.router import get_event_ingress

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


def cmd_router(args: argparse.Namespace) -> int:
    from interfaces.ingress.router_consumer import run_router_consumer

    processed = run_router_consumer(idle_timeout=args.idle_timeout)
    print(json.dumps({"processed": processed}, indent=2, ensure_ascii=False))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from cys_core.observability.prometheus_setup import cleanup_multiproc_dir_on_startup

    cleanup_multiproc_dir_on_startup()
    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.port,
        workers=max(1, args.workers),
    )
    return 0


def cmd_session(args: argparse.Namespace) -> int:
    import asyncio

    from bootstrap.container import get_container
    from cys_core.domain.engagement.models import EngagementMode, EngagementRequest, PlanStrategy

    async def _run():
        start = get_container().get_start_engagement()
        request = EngagementRequest(
            goal=args.goal,
            plan_strategy=PlanStrategy.META_LLM,
            mode=EngagementMode.ASYNC,
        )
        return await start.execute(request)

    engagement, decision, job_ids = asyncio.run(_run())
    print(
        json.dumps(
            {
                "engagement_id": engagement.id,
                "status": engagement.status.value,
                "routing": decision.model_dump(),
                "job_ids": job_ids,
                "message": "Engagement jobs enqueued. Run: uv run egregore worker --max-jobs N",
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def cmd_adversarial_test(_args: argparse.Namespace) -> int:
    import pytest

    return pytest.main(["-q", "tests"])


def cmd_catalog_seed(_args: argparse.Namespace) -> int:
    result = get_container().get_seed_catalog().execute()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def cmd_migrate(_args: argparse.Namespace) -> int:
    from cys_core.infrastructure.migrations.runner import apply_migrations
    from cys_core.observability.logging_setup import configure_logging
    from cys_core.observability.otel import setup_otel

    get_container()
    configure_logging("egregore-migrate")
    setup_otel(service_name="egregore-migrate")

    applied = apply_migrations(settings.postgres_url)
    get_container().get_trace_backend().flush()
    print(json.dumps({"applied": applied}, indent=2, ensure_ascii=False))
    return 0


def cmd_info(_args: argparse.Namespace) -> int:
    registry = get_agent_registry()
    print(
        json.dumps(
            {
                "project": "egregore",
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
                "persistence_connector": settings.persistence_connector,
                "job_store_connector": settings.job_store_connector,
                "siem_adapter": settings.siem_adapter,
                "use_real_embeddings": settings.use_real_embeddings,
                "use_kafka": settings.use_kafka,
                "kafka_bootstrap_servers": settings.kafka_bootstrap_servers,
                "agents_root": settings.agents_root,
            },
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Egregore event-driven multi-agent platform")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Ingest structured security event and enqueue worker jobs")
    ingest.add_argument("--type", "-t", required=True, help="Event type (e.g. siem.alert)")
    ingest.add_argument("--payload", "-p", required=True, help="JSON payload or raw text")
    ingest.add_argument("--severity", "-s", default="medium")
    ingest.add_argument("--source", default="")
    ingest.add_argument("--event-id", default=None)
    ingest.set_defaults(func=cmd_ingest)

    router = sub.add_parser("router", help="Run Kafka router consumer daemon")
    router.add_argument("--idle-timeout", type=float, default=0.0, help="Exit after N seconds idle (0=run forever)")
    router.set_defaults(func=cmd_router)

    serve = sub.add_parser("serve", help="Start FastAPI event/status server")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8080)
    serve.add_argument("--workers", type=int, default=1)
    serve.set_defaults(func=cmd_serve)

    session = sub.add_parser("session", help="Manual investigation — enqueue all workers")
    session.add_argument("--goal", "-g", required=True, help="Investigation goal")
    session.set_defaults(func=cmd_session)

    adv = sub.add_parser("adversarial-test", help="Run security test suite")
    adv.set_defaults(func=cmd_adversarial_test)

    info = sub.add_parser("info", help="Show configuration summary")
    info.set_defaults(func=cmd_info)

    migrate = sub.add_parser("migrate", help="Apply SQL migrations to Postgres")
    migrate.set_defaults(func=cmd_migrate)

    catalog = sub.add_parser("catalog", help="Catalog operations")
    catalog_sub = catalog.add_subparsers(dest="catalog_cmd", required=True)
    catalog_seed = catalog_sub.add_parser("seed", help="Seed catalog from agents/ profile pack")
    catalog_seed.set_defaults(func=cmd_catalog_seed)

    return parser


def main() -> None:
    # Ensure bootstrap wiring runs for ALL CLI commands (incl. migrate/serve),
    # so registries/loaders are configured in offline/production environments.
    register_multiprocess_shutdown()
    from bootstrap.container import get_container

    get_container()
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
