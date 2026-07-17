from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any


def create_approval_id() -> str:
    return f"appr-{uuid.uuid4().hex[:12]}"


def params_hash(tool_args: dict[str, Any]) -> str:
    payload = json.dumps(tool_args, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()
