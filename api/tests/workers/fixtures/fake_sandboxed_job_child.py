"""Stand-in child process for SubprocessExecutionBackend tests.

Mimics the stdin-envelope-in / stdout-RunResult-out contract of
`egregore run-sandboxed-job` without needing a live container/Postgres, so
SubprocessExecutionBackend's own plumbing (spawn, stdin write, stdout parse,
non-zero exit handling, kill-on-cancel) can be tested in isolation from the
real CLI's implementation.
"""

from __future__ import annotations

import json
import sys
import time


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "echo"
    envelope = json.loads(sys.stdin.read())
    job = envelope["job"]

    if mode == "hang":
        time.sleep(3600)
        return 0
    if mode == "garbage":
        print("not json{{{")
        return 0
    if mode == "crash":
        print("boom", file=sys.stderr)
        return 2

    result = {
        "job_id": job["job_id"],
        "persona": job["persona"],
        "success": mode != "fail",
        "finding": {},
        "error": "" if mode != "fail" else "simulated_failure",
        "sandbox_id": "",
    }
    print(json.dumps({"result": result}))
    return 0 if mode != "fail" else 1


if __name__ == "__main__":
    sys.exit(main())
