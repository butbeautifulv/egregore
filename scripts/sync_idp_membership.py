#!/usr/bin/env python3
from __future__ import annotations

import argparse

from bootstrap.container import get_container
from cys_core.application.authz.idp_sync import IdpGroupMapping, membership_tuples_for_user, platform_admin_tuples


def _parse_mapping(raw: str) -> IdpGroupMapping:
    group, organization_id, *rest = raw.split(":")
    relation = rest[0] if rest else "member"
    return IdpGroupMapping(group=group, organization_id=organization_id, relation=relation)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync IdP group membership to OpenFGA tuples.")
    parser.add_argument("--user", required=True, help="IdP subject/user id")
    parser.add_argument("--group", action="append", default=[], help="Group assigned to the user; repeatable")
    parser.add_argument(
        "--map",
        action="append",
        default=[],
        help="Mapping in group:organization_id[:member|admin] form; repeatable",
    )
    parser.add_argument(
        "--platform-admin",
        action="store_true",
        help="Map user to organization:platform#admin. Does not grant datasource permissions.",
    )
    parser.add_argument("--write", action="store_true", help="Write tuples via configured AuthzService")
    args = parser.parse_args()

    mappings = [_parse_mapping(item) for item in args.map]
    tuples = membership_tuples_for_user(user_id=args.user, groups=args.group, mappings=mappings)
    if args.platform_admin:
        tuples.extend(platform_admin_tuples(user_id=args.user))

    if args.write:
        get_container().get_authz_service().write_tuples(tuples)
        print(f"wrote {len(tuples)} tuples")
    else:
        for item in tuples:
            print(f"{item.object}#{item.relation}@{item.user}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
