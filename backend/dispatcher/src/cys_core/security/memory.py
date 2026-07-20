from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cys_core.domain.memory.validator import MemoryEntryValidator


class SecureAgentMemory:
    """Validated, isolated agent memory (cheat sheet §3)."""

    MAX_MEMORY_ITEMS = 100
    MAX_ITEM_LENGTH = MemoryEntryValidator.MAX_ITEM_LENGTH
    MEMORY_TTL_HOURS = 24

    def __init__(self, user_id: str, signing_key: bytes | None = None) -> None:
        self.user_id = user_id
        self.signing_key = signing_key or b"cys-agi-default-key"
        self.memories: list[dict] = []
        self._validator = MemoryEntryValidator(namespace_key=user_id, signing_key=self.signing_key)

    def add(self, content: str, memory_type: str = "conversation") -> None:
        validated = self._validator.validate(content)
        if validated.rejected or not validated.content:
            return
        entry = {
            "content": validated.content,
            "type": memory_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": self.user_id,
            "checksum": validated.checksum,
        }
        self.memories.append(entry)
        self._enforce_limits()

    def get_context(self) -> list[str]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.MEMORY_TTL_HOURS)
        valid: list[str] = []
        for mem in self.memories:
            mem_time = datetime.fromisoformat(mem["timestamp"])
            if mem_time > cutoff and self._validator.verify_checksum(mem["content"], mem.get("checksum", "")):
                valid.append(mem["content"])
        return valid

    def _compute_checksum(self, content: str) -> str:
        return self._validator.checksum(content)

    def _enforce_limits(self) -> None:
        if len(self.memories) > self.MAX_MEMORY_ITEMS:
            self.memories = self.memories[-self.MAX_MEMORY_ITEMS :]
