#!/usr/bin/env python3
"""Normalize agent catalog payloads to persona_prompt-only storage."""

from __future__ import annotations

import argparse
import json
import sys

from cys_core.domain.catalog.models import AgentCatalogEntry, ProfilePack
from cys_core.domain.security.system_prompt_assembler import (
    assemble_trusted_system_context,
    extract_persona_prompt,
)


def migrate_agent_payload(payload: dict) -> dict:
    persona = payload.get("persona_prompt") or extract_persona_prompt(payload.get("system_prompt", ""))
    language = payload.get("language", "ru")
    ctx = assemble_trusted_system_context(persona, language=language)
    updated = dict(payload)
    updated["persona_prompt"] = persona
    updated["language"] = language
    updated["system_prompt"] = ""
    updated["system_prompt_digest"] = ctx.digest
    return updated


def migrate_profile_payload(payload: dict) -> dict:
    updated = dict(payload)
    updated["global_rules"] = ""
    return updated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate catalog JSON payloads to persona-only prompts.")
    parser.add_argument("--agents", type=str, help="Path to JSON list of agent payloads")
    parser.add_argument("--profiles", type=str, help="Path to JSON list of profile payloads")
    parser.add_argument("--apply", action="store_true", help="Write migrated JSON to stdout paths (.migrated suffix)")
    args = parser.parse_args(argv)

    if not args.agents and not args.profiles:
        parser.error("Provide --agents and/or --profiles")

    if args.agents:
        agents_path = args.agents
        agents = json.loads(open(agents_path, encoding="utf-8").read())
        migrated = [migrate_agent_payload(item) for item in agents]
        for item in migrated:
            AgentCatalogEntry.model_validate(item)
        if args.apply:
            out = agents_path + ".migrated"
            open(out, "w", encoding="utf-8").write(json.dumps(migrated, indent=2))
            print(f"wrote {out}", file=sys.stderr)
        else:
            print(json.dumps(migrated, indent=2))

    if args.profiles:
        profiles_path = args.profiles
        profiles = json.loads(open(profiles_path, encoding="utf-8").read())
        migrated_profiles = [migrate_profile_payload(item) for item in profiles]
        for item in migrated_profiles:
            ProfilePack.model_validate(item)
        if args.apply:
            out = profiles_path + ".migrated"
            open(out, "w", encoding="utf-8").write(json.dumps(migrated_profiles, indent=2))
            print(f"wrote {out}", file=sys.stderr)
        else:
            print(json.dumps(migrated_profiles, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
