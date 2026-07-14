from __future__ import annotations

import base64
import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from cys_core.application.runtime_config import (
    get_e2b_api_key,
    get_python_sandbox_image,
    get_python_sandbox_timeout,
    get_stage,
)


def _e2b_execute(code: str) -> dict[str, Any]:
    try:
        import importlib

        Sandbox = importlib.import_module("e2b_code_interpreter").Sandbox

        with Sandbox(api_key=get_e2b_api_key()) as sandbox:
            execution = sandbox.run_code(code, timeout=int(get_python_sandbox_timeout()))
            return {
                "success": not execution.error,
                "stdout": (execution.logs.stdout or [])[-20:],
                "stderr": (execution.logs.stderr or [])[-10:],
                "provider": "e2b",
            }
    except ImportError:
        return {"success": False, "error": "e2b_code_interpreter package not installed"}
    except Exception as exc:
        return {"success": False, "error": str(exc), "provider": "e2b"}


def python_sandbox(code: str) -> dict[str, Any]:
    """Execute LLM-generated Python inside an isolated sandbox.

    Prefers E2B (managed microVM) when configured. Otherwise runs in a throwaway,
    locked-down Docker container (no network, read-only rootfs, dropped caps,
    non-root). NEVER falls back to bare host `subprocess` — arbitrary
    model-authored code must not execute with the worker process's privileges.
    """
    if get_e2b_api_key():
        result = _e2b_execute(code)
        if result.get("success") or get_stage() == "prod":
            return result
        # E2B configured but failed in a non-prod stage: fall through to the Docker
        # sandbox rather than silently returning the E2B error.
    if not code.strip():
        return {"success": False, "error": "empty code"}

    from cys_core.infrastructure.tools.adapters.docker_sandbox import run_python_in_docker

    return run_python_in_docker(
        code,
        timeout=get_python_sandbox_timeout(),
        image=get_python_sandbox_image(),
    )


def vision_analyze(path: str, question: str = "Describe this image in detail.") -> dict[str, Any]:
    """Basic image analysis — metadata + optional LLM vision when file is readable."""
    file_path = Path(path).expanduser()
    if not file_path.is_file():
        return {"success": False, "error": f"file not found: {path}"}
    suffix = file_path.suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        return {"success": False, "error": "vision_analyze supports image files only"}
    try:
        from cys_core.llm.reasoning import get_reasoning_model_connector

        model = get_reasoning_model_connector().create_model()
        data = base64.b64encode(file_path.read_bytes()).decode("ascii")
        mime = "image/png" if suffix == ".png" else "image/jpeg"
        response = model.invoke(
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}},
                    ],
                }
            ]
        )
        text = str(getattr(response, "content", response))
        return {"success": True, "path": str(file_path), "analysis": text}
    except Exception as exc:
        return {
            "success": False,
            "path": str(file_path),
            "error": str(exc),
            "note": "Vision model unavailable; use read_document or external OCR.",
        }


def search_archived_webpage(url: str, timestamp: str = "") -> dict[str, Any]:
    """Fetch closest Wayback Machine snapshot for historical web content."""
    if not url.strip():
        return {"success": False, "error": "url required"}
    params = {"url": url}
    if timestamp:
        params["timestamp"] = timestamp
    api = "https://archive.org/wayback/available?" + urllib.parse.urlencode(params)
    try:
        from bootstrap.settings import get_settings

        timeout_s = get_settings().wayback_api_timeout_s
        with urllib.request.urlopen(api, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {"success": False, "error": str(exc)}
    closest = (data.get("archived_snapshots") or {}).get("closest") or {}
    if not closest.get("available"):
        return {"success": False, "error": "no archived snapshot", "raw": data}
    return {
        "success": True,
        "url": url,
        "archived_url": closest.get("url", ""),
        "timestamp": closest.get("timestamp", ""),
        "status": closest.get("status", ""),
    }
