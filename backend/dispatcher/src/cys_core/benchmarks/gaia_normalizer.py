from __future__ import annotations

import re
from datetime import datetime


def normalize_gaia_answer(raw: str, *, answer_type: str = "string") -> str:
    text = raw.strip()
    boxed = re.search(r"\\boxed\{([^}]+)\}", text)
    if boxed:
        text = boxed.group(1).strip()
    text = text.strip().strip(".").strip()
    kind = answer_type.lower()
    if kind == "number":
        match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
        return match.group(0) if match else text
    if kind == "date":
        for fmt in ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%d %B %Y"):
            try:
                return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return text.lower()
    if kind == "time":
        return re.sub(r"\s+", "", text.lower())
    return text.lower()


def score_gaia(prediction: str, reference: str, *, answer_type: str = "string") -> bool:
    return normalize_gaia_answer(prediction, answer_type=answer_type) == normalize_gaia_answer(
        reference, answer_type=answer_type
    )
