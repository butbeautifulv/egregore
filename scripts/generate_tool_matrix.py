#!/usr/bin/env python3
"""Generate docs/tool-matrix.md from ToolProvider metadata."""

from __future__ import annotations

from pathlib import Path

from cys_core.application.tools.tool_matrix import render_tool_matrix_markdown

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "tool-matrix.md"


def main() -> None:
    OUTPUT.write_text(render_tool_matrix_markdown(), encoding="utf-8")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
