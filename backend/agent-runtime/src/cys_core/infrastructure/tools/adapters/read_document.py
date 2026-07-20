from __future__ import annotations

from pathlib import Path
from typing import Any


def read_document(path: str, *, max_chars: int = 12000) -> dict[str, Any]:
    """Read local document text (txt, md, json, csv) for research/DFIR workflows."""
    file_path = Path(path).expanduser()
    if not file_path.is_file():
        return {"success": False, "error": f"file not found: {path}"}
    suffix = file_path.suffix.lower()
    try:
        if suffix in {".txt", ".md", ".json", ".csv", ".log", ".yaml", ".yml"}:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        elif suffix == ".pdf":
            text = _read_pdf_stub(file_path)
        else:
            text = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return {"success": False, "error": str(exc)}
    truncated = len(text) > max_chars
    if truncated:
        text = text[:max_chars] + "\n...[truncated]"
    return {
        "success": True,
        "path": str(file_path.resolve()),
        "suffix": suffix,
        "truncated": truncated,
        "content": text,
    }


def _read_pdf_stub(file_path: Path) -> str:
    raw = file_path.read_bytes()
    # Minimal text extraction for text-based PDF streams (not full parser).
    chunks: list[str] = []
    for part in raw.split(b"stream"):
        if b"endstream" not in part:
            continue
        body = part.split(b"endstream", 1)[0]
        try:
            decoded = body.decode("latin-1", errors="ignore")
        except Exception:
            continue
        if any(c.isalpha() for c in decoded):
            chunks.append(decoded)
    if chunks:
        return "\n".join(chunks)
    return f"[PDF file {file_path.name}: install a PDF parser for full extraction; binary length={len(raw)}]"
