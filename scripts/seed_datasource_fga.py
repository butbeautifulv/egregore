#!/usr/bin/env python3
"""Seed organization-owned datasource FGA objects (Phase 5.0)."""

from __future__ import annotations

import argparse

from bootstrap.container import get_container
from cys_core.application.ports.authz import AuthzTuple
from cys_core.domain.authz.tool_datasource_map import datasource_seed_tuples


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed datasource FGA ownership tuples.")
    parser.add_argument("--organization", default="default", help="Organization id")
    parser.add_argument("--write", action="store_true", help="Write tuples via AuthzService")
    args = parser.parse_args()

    tuples = [
        AuthzTuple(user=user, relation=relation, object=obj)
        for user, relation, obj in datasource_seed_tuples(args.organization)
    ]
    if args.write:
        get_container().get_authz_service().write_tuples(tuples)
        print(f"wrote {len(tuples)} datasource tuples for org={args.organization}")
    else:
        for item in tuples:
            print(f"{item.object}#{item.relation}@{item.user}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
