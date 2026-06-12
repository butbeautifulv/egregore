#!/usr/bin/env python3
"""CI gate: agent.yaml policy fields require adversarial test updates in the same change."""

from __future__ import annotations

import re
import subprocess
import sys

POLICY_FIELDS = (
    "tools:",
    "hitl_tools:",
    "trust_level:",
    "bus_recipients:",
    "skills:",
)
AGENT_GLOB = "agents/**/agent.yaml"
ADVERSARIAL_PREFIX = "tests/adversarial/"


def _git_diff_names(base: str, head: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...{head}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _policy_lines_changed(path: str, base: str, head: str) -> bool:
    result = subprocess.run(
        ["git", "diff", f"{base}...{head}", "--", path],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False
    for line in result.stdout.splitlines():
        if not line.startswith(("+", "-")) or line.startswith(("+++", "---")):
            continue
        body = line[1:].strip()
        if any(body.startswith(field) for field in POLICY_FIELDS):
            return True
        if re.search(r"^\s*-\s+\S+", body) and path.endswith("agent.yaml"):
            # tool list entry add/remove
            if "tools" in result.stdout or "skills" in result.stdout or "hitl_tools" in result.stdout:
                return True
    return False


def check_policy_tests_updated(base: str, head: str = "HEAD") -> int:
    changed = _git_diff_names(base, head)
    agent_files = [name for name in changed if name.endswith("agent.yaml") and name.startswith("agents/")]
    if not agent_files:
        return 0

    policy_touched = any(_policy_lines_changed(path, base, head) for path in agent_files)
    if not policy_touched:
        return 0

    adversarial_touched = any(name.startswith(ADVERSARIAL_PREFIX) for name in changed)
    if adversarial_touched:
        return 0

    print(
        "Agent policy drift detected: agent.yaml tools/hitl/trust/bus/skills changed "
        f"without updates under {ADVERSARIAL_PREFIX}",
        file=sys.stderr,
    )
    for path in agent_files:
        print(f"  - {path}", file=sys.stderr)
    return 1


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "HEAD~1"
    head = sys.argv[2] if len(sys.argv) > 2 else "HEAD"
    return check_policy_tests_updated(base, head)


if __name__ == "__main__":
    raise SystemExit(main())
