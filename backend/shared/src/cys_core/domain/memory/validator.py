from __future__ import annotations

import hashlib
from dataclasses import dataclass

from cys_core.domain.security.redaction import RedactionService
from cys_core.domain.security.sanitizer import InjectionVerdict, InputSanitizer


@dataclass(frozen=True)
class ValidatedMemoryContent:
    content: str
    checksum: str
    rejected: bool = False


class MemoryEntryValidator:
    """Sanitize and checksum memory content before persistence."""

    MAX_ITEM_LENGTH = 5000

    def __init__(
        self,
        *,
        namespace_key: str,
        signing_key: bytes | None = None,
        sanitizer: InputSanitizer | None = None,
        redaction: RedactionService | None = None,
    ) -> None:
        self.namespace_key = namespace_key
        self.signing_key = signing_key or b"cys-agi-default-key"
        self._sanitizer = sanitizer or InputSanitizer()
        self._redaction = redaction or RedactionService()

    def validate(self, content: str) -> ValidatedMemoryContent:
        if self._sanitizer.classify(content) is not InjectionVerdict.NONE:
            return ValidatedMemoryContent(content="", checksum="", rejected=True)
        if len(content) > self.MAX_ITEM_LENGTH:
            content = content[: self.MAX_ITEM_LENGTH]
        if self._redaction.contains_sensitive_data(content):
            content = self._redaction.redact_pii(content)
        content = self._sanitizer.filter_patterns(content)
        return ValidatedMemoryContent(content=content, checksum=self.checksum(content), rejected=False)

    def checksum(self, content: str) -> str:
        payload = (content + self.namespace_key).encode() + self.signing_key
        return hashlib.sha256(payload).hexdigest()[:16]

    def verify_checksum(self, content: str, checksum: str) -> bool:
        return self.checksum(content) == checksum
