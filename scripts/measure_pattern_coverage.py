#!/usr/bin/env python3
# ruff: noqa: E402
"""Measure sanitizer detection rate on docs/injections/ — metadata only, no content output."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Add project root for imports when run as script.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from cys_core.domain.security.sanitizer import InputSanitizer  # noqa: E402

CORPUS_ROOT = _ROOT / "docs" / "injections"
# Structural lines likely to contain technique markers (not full-file classification).
_MARKER = re.compile(
    r"<\|[^|]+\|>|!UNRESTRICTED|!UNFILTERED|!LEAK|GODMODE|improve and structure|"
    r"BEGIN\s+OPENAI|interaction-config|Born Survivalists|jailbreak|<<SYS>>|"
    r"ignore\s+.*instructions|system\s+override",
    re.IGNORECASE,
)
_CHUNK_SIZE = 240


def _iter_probe_chunks(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    chunks: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if len(stripped) < 24 or not _MARKER.search(stripped):
            continue
        chunks.append(stripped[:_CHUNK_SIZE])
    if not chunks and len(text) > 80:
        for i in range(0, min(len(text), 2000), _CHUNK_SIZE):
            chunks.append(text[i : i + _CHUNK_SIZE])
    return chunks[:20]


def main() -> int:
    if not CORPUS_ROOT.is_dir():
        print(json.dumps({"error": f"corpus not found: {CORPUS_ROOT}"}))
        return 1

    sanitizer = InputSanitizer()
    files_report: list[dict[str, object]] = []
    totals = {"hard": 0, "soft": 0, "none": 0, "probes": 0}

    for path in sorted(CORPUS_ROOT.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".mkd", ".md", ".txt", ".json"}:
            continue
        rel = str(path.relative_to(CORPUS_ROOT))
        counts = {"hard": 0, "soft": 0, "none": 0}
        for chunk in _iter_probe_chunks(path):
            verdict = sanitizer.classify(chunk)
            counts[verdict.value] += 1
            totals[verdict.value] += 1
            totals["probes"] += 1
        if sum(counts.values()):
            detected = counts["hard"] + counts["soft"]
            files_report.append(
                {
                    "file": rel,
                    "probes": sum(counts.values()),
                    "hard": counts["hard"],
                    "soft": counts["soft"],
                    "none": counts["none"],
                    "detection_rate": round(detected / sum(counts.values()), 3),
                }
            )

    detected_total = totals["hard"] + totals["soft"]
    summary = {
        "corpus_root": str(CORPUS_ROOT),
        "files_analyzed": len(files_report),
        "probes": totals["probes"],
        "hard": totals["hard"],
        "soft": totals["soft"],
        "none": totals["none"],
        "overall_detection_rate": round(detected_total / totals["probes"], 3) if totals["probes"] else 0.0,
        "files": files_report,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
