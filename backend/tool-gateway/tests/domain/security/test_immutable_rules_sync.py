from pathlib import Path

import pytest

from cys_core.domain.security.immutable_rules import GLOBAL_RULES_BODY

PROJECT_ROOT = Path(__file__).resolve().parents[4]
RULES_DIR = PROJECT_ROOT / "agents" / "rules"
RULES_SKIP = frozenset({"README.md"})


def _rules_markdown_block() -> str:
    sections: list[str] = []
    for path in sorted(RULES_DIR.glob("*.md")):
        if path.name in RULES_SKIP:
            continue
        sections.append(path.read_text(encoding="utf-8").strip())
    return "\n\n".join(sections)


@pytest.mark.unit
def test_global_rules_body_contains_markdown_phrases():
    md = _rules_markdown_block()
    for phrase in (
        "Output conventions",
        "Assessment scope rules",
        "Security rules (all agents)",
        "Respond in Russian",
        "explicitly authorized",
        "High-risk tools",
    ):
        assert phrase in md
        assert phrase in GLOBAL_RULES_BODY
