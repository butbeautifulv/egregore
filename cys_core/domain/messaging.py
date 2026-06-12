from __future__ import annotations

from typing import Any


def extract_message_content(content: str | list[Any]) -> str:
    """Normalize chat message content blocks to plain text."""
    if isinstance(content, list):
        return "".join(block.get("text", "") if isinstance(block, dict) else str(block) for block in content)
    return str(content)
