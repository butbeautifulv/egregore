#!/usr/bin/env python3
"""Offline metadata triage for docs/injections/ — never prints file contents."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

CORPUS_ROOT = Path(__file__).resolve().parents[1] / "docs" / "injections"
ZERO_WIDTH = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]")
BASE64_BLOB = re.compile(r"[A-Za-z0-9+/]{32,}={0,2}")
CYRILLIC = re.compile(r"[\u0400-\u04FF]")
CJK = re.compile(r"[\u4e00-\u9fff]")
LATIN = re.compile(r"[A-Za-z]")


def _detect_scripts(text: str) -> list[str]:
    scripts: list[str] = []
    if LATIN.search(text):
        scripts.append("latin")
    if CYRILLIC.search(text):
        scripts.append("cyrillic")
    if CJK.search(text):
        scripts.append("cjk")
    return scripts or ["other"]


def triage_file(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="ignore")
    return {
        "path": str(path.relative_to(CORPUS_ROOT)),
        "size_bytes": len(raw),
        "scripts": _detect_scripts(text),
        "has_zero_width": bool(ZERO_WIDTH.search(text)),
        "has_base64_blob": bool(BASE64_BLOB.search(text)),
    }


def main() -> int:
    if not CORPUS_ROOT.is_dir():
        print(json.dumps({"error": f"corpus not found: {CORPUS_ROOT}", "file_count": 0}))
        return 1

    files = [p for p in CORPUS_ROOT.rglob("*") if p.is_file()]
    entries = [triage_file(p) for p in sorted(files)]
    summary = {
        "corpus_root": str(CORPUS_ROOT),
        "file_count": len(entries),
        "with_zero_width": sum(1 for e in entries if e["has_zero_width"]),
        "with_base64_blob": sum(1 for e in entries if e["has_base64_blob"]),
        "scripts_seen": sorted({s for e in entries for s in e["scripts"]}),
        "files": entries,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
