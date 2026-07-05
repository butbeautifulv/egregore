from __future__ import annotations

import argparse
import json
import sys

from bootstrap.catalog_loader import load_profile_pack
from bootstrap.container import get_container
from bootstrap.policy_defaults import default_profile_policy
from cys_core.application.use_cases.seed_catalog import SeedCatalog
from cys_core.application.use_cases.upsert_profile_policy import UpsertProfilePolicy
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.infrastructure.catalog.catalog_registry import get_agent_catalog, get_catalog_version_metric, reload_agent_registry
from cys_core.infrastructure.catalog.profile_policy import get_profile_policy


def cmd_seed(_args: argparse.Namespace) -> int:
    from cys_core.infrastructure.catalog.tool_catalog_seed import load_tools_for_seed

    container = get_container()
    result = SeedCatalog(
        container.get_agent_catalog(),
        tool_catalog=container.get_tool_catalog(),
        seed_loaders=container.get_catalog_seed_loaders_port(),
        load_profile_pack=load_profile_pack,
        load_tools_for_seed=load_tools_for_seed,
        reload=reload_agent_registry,
        mutation=container.get_catalog_mutation_service(),
    ).execute()
    print(json.dumps(result, indent=2, default=str))
    return 0


def cmd_reload(_args: argparse.Namespace) -> int:
    reload_agent_registry()
    print(json.dumps({"status": "reloaded", "version": get_catalog_version_metric()}))
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    catalog = get_agent_catalog()
    agents = catalog.list_agents(enabled_only=False)
    print(
        json.dumps(
            {
                "version": get_catalog_version_metric(),
                "agents": len(agents),
                "enabled": sum(1 for agent in agents if agent.enabled),
            },
            indent=2,
        )
    )
    return 0


def cmd_policy_diff(args: argparse.Namespace) -> int:
    live = get_profile_policy(args.profile_id).model_dump()
    seed = default_profile_policy().model_dump()
    diff = {
        key: {"live": live.get(key), "seed": seed.get(key)}
        for key in sorted(set(live) | set(seed))
        if live.get(key) != seed.get(key)
    }
    print(json.dumps({"profile_id": args.profile_id, "diff": diff}, indent=2, default=str))
    return 0


def cmd_policy_apply(args: argparse.Namespace) -> int:
    UpsertProfilePolicy(
        get_agent_catalog(),
        policy_merge=get_container().get_policy_merge_port(),
        policy_defaults=get_container().get_policy_defaults_port(),
        mutation=get_container().get_catalog_mutation_service(),
        reload=reload_agent_registry,
    ).apply_seed_defaults(args.profile_id, actor="cli")
    print(json.dumps({"profile_id": args.profile_id, "applied": True}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="egregore-catalog")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed").set_defaults(func=cmd_seed)
    sub.add_parser("reload").set_defaults(func=cmd_reload)
    sub.add_parser("status").set_defaults(func=cmd_status)
    policy = sub.add_parser("policy")
    policy_sub = policy.add_subparsers(dest="policy_command", required=True)
    diff = policy_sub.add_parser("diff")
    diff.add_argument("--profile-id", default=DEFAULT_PROFILE_ID)
    diff.set_defaults(func=cmd_policy_diff)
    apply_cmd = policy_sub.add_parser("apply")
    apply_cmd.add_argument("--profile-id", default=DEFAULT_PROFILE_ID)
    apply_cmd.set_defaults(func=cmd_policy_apply)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
