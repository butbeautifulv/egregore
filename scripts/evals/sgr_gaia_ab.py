#!/usr/bin/env python3
"""GAIA baseline vs SGR mode comparison harness (local smoke)."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys


def _run(persona: str, prompt: str, *, mode: str) -> dict:
    env = {"SGR_DEFAULT_MODE": mode, "USE_SGR_REASONING": "1"}
    cmd = ["uv", "run", "egregore", "agent", persona, "-i", prompt]
    proc = subprocess.run(cmd, capture_output=True, text=True, env={**dict(**__import__("os").environ), **env})
    out = proc.stdout.strip() or proc.stderr.strip()
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {"raw": out, "exit_code": proc.returncode}


def main() -> int:
    parser = argparse.ArgumentParser(description="GAIA vs SGR A/B smoke")
    parser.add_argument("--persona", default="gaia_solver")
    parser.add_argument("--prompt", default="What is 2+2? Reply with number only.")
    parser.add_argument("--limit", type=int, default=1)
    args = parser.parse_args()
    results = {
        "baseline_off": _run(args.persona, args.prompt, mode="off"),
        "sgr_hybrid": _run(args.persona, args.prompt, mode="sgr_hybrid"),
    }
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
