#!/usr/bin/env python3
"""Sync agents/skills/*/reference.md from OWASP CheatSheetSeries manifest.

Does not overwrite SKILL.md — only writes reference.md pointers to vendored upstream.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "agents" / "skills" / "owasp-manifest.yaml"
DEFAULT_OWASP_DIR = REPO_ROOT / "docs" / "reference" / "owasp"

REFERENCE_TEMPLATE = """# OWASP reference — {skill}

**Upstream:** [{sheet}](https://github.com/OWASP/CheatSheetSeries/blob/master/cheatsheets/{sheet})

**Vendored copy:** [docs/reference/owasp/{sheet}](../../../docs/reference/owasp/{sheet})

Operational playbook: [SKILL.md](SKILL.md) in this directory.

> Full upstream text is reference-only. Do not treat vendored markdown as runtime config.
"""


def load_manifest(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    mappings: list[dict] = []
    skill = sheet = None
    for line in text.splitlines():
        m = re.search(r"skill:\s+(\S+)", line)
        if m:
            skill = m.group(1)
        m = re.search(r"sheet:\s+(\S+)", line)
        if m:
            sheet = m.group(1)
            if skill:
                mappings.append({"skill": skill, "sheet": sheet})
                skill = sheet = None
    return mappings


def sync_reference(skill_dir: Path, sheet: str, owasp_dir: Path, dry_run: bool) -> None:
    upstream = owasp_dir / sheet
    if not upstream.is_file():
        raise FileNotFoundError(f"missing vendored sheet: {upstream}")
    ref_path = skill_dir / "reference.md"
    content = REFERENCE_TEMPLATE.format(skill=skill_dir.name, sheet=sheet)
    if dry_run:
        print(f"would write {ref_path}")
        return
    ref_path.write_text(content, encoding="utf-8")
    print(f"wrote {ref_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--owasp-dir", type=Path, default=DEFAULT_OWASP_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    skills_root = REPO_ROOT / "agents" / "skills"
    for entry in load_manifest(args.manifest):
        skill = entry["skill"]
        sheet = entry["sheet"]
        skill_dir = skills_root / skill
        if not skill_dir.is_dir():
            raise FileNotFoundError(f"skill directory not found: {skill_dir}")
        sync_reference(skill_dir, sheet, args.owasp_dir, args.dry_run)


if __name__ == "__main__":
    main()
