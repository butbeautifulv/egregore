from __future__ import annotations

from pathlib import Path


def _file_type(path: str) -> str:
    ext = Path(path).suffix.lower().lstrip(".")
    if ext in {"jpg", "jpeg", "png", "gif", "webp"}:
        return "image"
    if ext in {"xlsx", "xls", "csv"}:
        return "spreadsheet"
    if ext in {"json", "jsonld"}:
        return "json"
    if ext == "pdf":
        return "pdf"
    if ext in {"docx", "doc"}:
        return "document"
    if ext in {"pptx", "ppt"}:
        return "presentation"
    if ext in {"html", "htm"}:
        return "html"
    if ext in {"wav", "mp3", "m4a"}:
        return "audio"
    if ext == "zip":
        return "archive"
    if ext in {"txt", "md", "log"}:
        return "text"
    return ext or "unknown"


def process_attachment_hints(paths: list[str]) -> list[str]:
    """Type-aware tool routing hints (DeepAgent process_input pattern)."""
    hints: list[str] = []
    for raw in paths:
        path = str(raw)
        kind = _file_type(path)
        if kind == "image":
            hints.append(f"{path}: use vision_analyze for charts/screenshots; read_document for OCR text fallback.")
        elif kind == "spreadsheet":
            hints.append(f"{path}: use read_document first; for calculations use python_sandbox (HITL).")
        elif kind == "json":
            hints.append(f"{path}: use read_document; parse structured fields with python_sandbox if needed.")
        elif kind in {"pdf", "document", "presentation", "html"}:
            hints.append(f"{path}: use read_document to extract text before synthesis.")
        elif kind == "audio":
            hints.append(f"{path}: use transcribe_audio tool, then analyze transcript.")
        elif kind == "archive":
            hints.append(f"{path}: archive file — extract contents before analysis (python_sandbox).")
        else:
            hints.append(f"{path}: use read_document for local file content.")
    return hints
