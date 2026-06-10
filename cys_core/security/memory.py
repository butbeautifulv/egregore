from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"disregard\s+(all\s+)?(previous|prior|system)\s+",
    r"you\s+are\s+now\s+",
]

SENSITIVE_PATTERNS = [
    r"\b\d{3}-\d{2}-\d{4}\b",
    r"\b\d{16}\b",
    r"password\s*[:=]\s*\S+",
    r"api[_-]?key\s*[:=]\s*\S+",
]


class SecureAgentMemory:
    """Validated, isolated agent memory (cheat sheet §3)."""

    MAX_MEMORY_ITEMS = 100
    MAX_ITEM_LENGTH = 5000
    MEMORY_TTL_HOURS = 24

    def __init__(self, user_id: str, signing_key: bytes | None = None) -> None:
        self.user_id = user_id
        self.signing_key = signing_key or b"cys-agi-default-key"
        self.memories: list[dict] = []

    def add(self, content: str, memory_type: str = "conversation") -> None:
        if self._contains_injection(content):
            return
        if len(content) > self.MAX_ITEM_LENGTH:
            content = content[: self.MAX_ITEM_LENGTH]
        if self._contains_sensitive_data(content):
            content = self._redact_sensitive_data(content)
        content = self._sanitize_injection_attempts(content)
        entry = {
            "content": content,
            "type": memory_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": self.user_id,
            "checksum": self._compute_checksum(content),
        }
        self.memories.append(entry)
        self._enforce_limits()

    def get_context(self) -> list[str]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.MEMORY_TTL_HOURS)
        valid: list[str] = []
        for mem in self.memories:
            mem_time = datetime.fromisoformat(mem["timestamp"])
            if mem_time > cutoff and self._verify_checksum(mem):
                valid.append(mem["content"])
        return valid

    def _contains_injection(self, content: str) -> bool:
        return any(re.search(p, content, re.I) for p in INJECTION_PATTERNS)

    def _contains_sensitive_data(self, content: str) -> bool:
        return any(re.search(p, content, re.I) for p in SENSITIVE_PATTERNS)

    def _redact_sensitive_data(self, content: str) -> str:
        for pattern in SENSITIVE_PATTERNS:
            content = re.sub(pattern, "[REDACTED]", content, flags=re.I)
        return content

    def _sanitize_injection_attempts(self, content: str) -> str:
        for pattern in INJECTION_PATTERNS:
            content = re.sub(pattern, "[FILTERED]", content, flags=re.I)
        return content

    def _compute_checksum(self, content: str) -> str:
        return hashlib.sha256((content + self.user_id).encode() + self.signing_key).hexdigest()[:16]

    def _verify_checksum(self, entry: dict) -> bool:
        expected = self._compute_checksum(entry["content"])
        return entry.get("checksum") == expected

    def _enforce_limits(self) -> None:
        if len(self.memories) > self.MAX_MEMORY_ITEMS:
            self.memories = self.memories[-self.MAX_MEMORY_ITEMS :]
