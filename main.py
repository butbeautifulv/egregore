from __future__ import annotations

import argparse
import json
import sys

from config import settings
from cys_core.registry.agents import get_agent_registry
from cys_core.runtime.agent import get_runtime


def cmd_assess(args: argparse.Namespace) -> int:
    from graph.workflow import run_assessment

    result = run_assessment(
        args.input,
        thread_id=args.thread_id,
        persistence=None,
    )
    if "__interrupt__" in result:
        print(json.dumps({"status": "pending_approval", "interrupt": str(result["__interrupt__"])}, indent=2, ensure_ascii=False))
        return 0
    print(json.dumps(result.get("report") or result, indent=2, ensure_ascii=False))
    return 0


def cmd_session(args: argparse.Namespace) -> int:
    from coordinator.deep_assessment import run_session

    result = run_session(args.goal, thread_id=args.thread_id)
    messages = result.get("messages", [])
    if messages:
        content = messages[-1].content
        print(content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))
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


def cmd_resume(args: argparse.Namespace) -> int:
    from graph.workflow import run_assessment

    resume_val = True if args.approve else {"approved": False}
    result = run_assessment("", thread_id=args.thread_id, resume=resume_val)
    print(json.dumps(result.get("report") or result, indent=2, ensure_ascii=False))
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
                "llm_provider": settings.llm_provider,
                "llm_model": settings.llm_model,
                "agents": registry.names(),
                "postgres_url": settings.postgres_url,
                "redis_url": settings.redis_url,
                "use_memory_fallback": settings.use_memory_fallback,
                "agents_root": settings.agents_root,
            },
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CYS-AGI secure multi-agent cybersecurity platform")
    sub = parser.add_subparsers(dest="command", required=True)

    registry = get_agent_registry()
    agent_names = [n for n in registry.names() if registry.get(n).role != "coordinator"]

    assess = sub.add_parser("assess", help="Run LangGraph security assessment pipeline")
    assess.add_argument("--input", "-i", required=True, help="Assessment input / signals")
    assess.add_argument("--thread-id", default="assess-001", help="Thread ID for persistence/HITL")
    assess.set_defaults(func=cmd_assess)

    session = sub.add_parser("session", help="Run Deep Agent long-running assessment session")
    session.add_argument("--goal", "-g", required=True, help="Assessment goal")
    session.add_argument("--thread-id", default="session-001", help="Session thread ID")
    session.set_defaults(func=cmd_session)

    agent = sub.add_parser("agent", help="Run a single specialist agent")
    agent.add_argument("name", choices=agent_names)
    agent.add_argument("--input", "-i", default=None, help="Input text (uses sample if omitted)")
    agent.set_defaults(func=cmd_agent)

    resume = sub.add_parser("resume", help="Resume assessment after HITL interrupt")
    resume.add_argument("--thread-id", required=True)
    resume.add_argument("--approve", action="store_true", help="Approve pending assessment")
    resume.set_defaults(func=cmd_resume)

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
