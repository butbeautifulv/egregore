#!/usr/bin/env python3
"""BFCL-lite baseline vs SGR comparison harness."""
from __future__ import annotations

import argparse
import json
import subprocess


SAMPLE = [
    {"category": "simple", "tool": "web_search", "prompt": "Search for CVE-2024-1234 summary"},
    {"category": "parallel", "tool": "read_document", "prompt": "Read document id doc-1"},
]


def _run(prompt: str, *, mode: str) -> dict:
    import os

    env = {**os.environ, "SGR_DEFAULT_MODE": mode, "USE_SGR_REASONING": "1"}
    proc = subprocess.run(
        ["uv", "run", "egregore", "agent", "consultant", "-i", prompt],
        capture_output=True,
        text=True,
        env=env,
    )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"raw": proc.stdout[:500], "exit_code": proc.returncode}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=2)
    args = parser.parse_args()
    rows = []
    for case in SAMPLE[: args.limit]:
        rows.append(
            {
                **case,
                "off": _run(case["prompt"], mode="off"),
                "sgr_iron": _run(case["prompt"], mode="iron"),
            }
        )
    print(json.dumps(rows, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
