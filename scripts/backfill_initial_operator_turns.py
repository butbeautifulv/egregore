#!/usr/bin/env python3
"""Backfill initial operator turns (wo-*) for legacy engagements with goal only."""

from __future__ import annotations

import argparse

from bootstrap.container import get_container
from cys_core.application.operator_messages.service import persist_operator_turn_to_memory
from cys_core.domain.follow_up.models import initial_follow_up_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", default="default")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    container = get_container()
    store = container.get_engagement_state_store()
    memory_reader = container.get_memory_read_service()
    memory_writer = container.get_memory_write_service()
    engagements = store.list_recent(args.tenant_id, limit=500)
    updated = 0
    for engagement in engagements:
        goal = (engagement.goal or "").strip()
        if not goal:
            continue
        turns = memory_reader.query_conversation_turns(args.tenant_id, engagement.id, limit=50)
        wo_id = initial_follow_up_id(engagement.id)
        has_initial = False
        for entry in turns:
            import json

            try:
                data = json.loads(entry.content)
            except json.JSONDecodeError:
                continue
            if str(data.get("follow_up_id", "")) == wo_id and data.get("role") == "operator":
                has_initial = True
                break
        if has_initial:
            continue
        if args.dry_run:
            print(f"would backfill {engagement.id}")
            updated += 1
            continue
        persist_operator_turn_to_memory(
            memory_writer,
            tenant_id=args.tenant_id,
            engagement_id=engagement.id,
            message=goal,
            follow_up_id=initial_follow_up_id(engagement.id),
            mode="auto",
            memory_reader=memory_reader,
            engagement_store=store,
        )
        updated += 1
        print(f"backfilled {engagement.id}")
    print(f"done: {updated} engagement(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
