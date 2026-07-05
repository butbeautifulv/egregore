from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from cys_core.domain.memory.models import InvestigationState, MemoryEntry, MemoryScope
from cys_core.domain.memory.validator import MemoryEntryValidator


class EpisodicMemoryReader(Protocol):
    def query(self, scope: MemoryScope, *, limit: int = 20) -> list[MemoryEntry]: ...


class EpisodicMemoryWriter(Protocol):
    def append(self, entry: MemoryEntry) -> None: ...


class InvestigationStateReader(Protocol):
    def get(self, tenant_id: str, investigation_id: str) -> InvestigationState | None: ...


class InvestigationStateWriter(Protocol):
    def upsert(self, state: InvestigationState) -> None: ...
    def append_finding(self, tenant_id: str, investigation_id: str, finding: dict[str, Any]) -> None: ...
    def mark_persona_done(self, tenant_id: str, investigation_id: str, persona: str) -> None: ...


class MemoryWriteService:
    """Validate and persist episodic memory entries."""

    def __init__(
        self,
        store: EpisodicMemoryWriter,
        *,
        signing_key: bytes | None = None,
    ) -> None:
        self.store = store
        self._signing_key = signing_key

    def _validator(self, scope: MemoryScope) -> MemoryEntryValidator:
        namespace = f"{scope.tenant_id}:{scope.investigation_id}"
        return MemoryEntryValidator(namespace_key=namespace, signing_key=self._signing_key)

    def append(
        self,
        *,
        scope: MemoryScope,
        content: str,
        memory_type: str,
        source_agent: str,
        source_job_id: str,
        trust_score: float = 1.0,
    ) -> MemoryEntry | None:
        validated = self._validator(scope).validate(content)
        if validated.rejected or not validated.content:
            return None
        entry = MemoryEntry(
            scope=scope,
            content=validated.content,
            memory_type=memory_type,  # type: ignore[arg-type]
            source_agent=source_agent,
            source_job_id=source_job_id,
            trust_score=trust_score,
            checksum=validated.checksum,
        )
        self.store.append(entry)
        return entry

    def append_finding(
        self,
        *,
        tenant_id: str,
        investigation_id: str,
        source_agent: str,
        source_job_id: str,
        finding: dict[str, Any],
        trust_score: float,
    ) -> MemoryEntry | None:
        scope = MemoryScope(tenant_id=tenant_id, investigation_id=investigation_id)
        content = json.dumps(finding, ensure_ascii=False)
        return self.append(
            scope=scope,
            content=content,
            memory_type="finding",
            source_agent=source_agent,
            source_job_id=source_job_id,
            trust_score=trust_score,
        )

    def append_pending_finding(
        self,
        *,
        tenant_id: str,
        investigation_id: str,
        source_agent: str,
        source_job_id: str,
        finding: dict[str, Any],
        trust_score: float = 0.3,
    ) -> MemoryEntry | None:
        scope = MemoryScope(tenant_id=tenant_id, investigation_id=investigation_id)
        content = json.dumps(finding, ensure_ascii=False)
        return self.append(
            scope=scope,
            content=content,
            memory_type="pending_finding",
            source_agent=source_agent,
            source_job_id=source_job_id,
            trust_score=trust_score,
        )


class MemoryReadService:
    """Retrieve investigation-scoped episodic memory with tenant isolation."""

    MEMORY_TTL_HOURS = 24 * 7

    def __init__(self, store: EpisodicMemoryReader, *, signing_key: bytes | None = None) -> None:
        self.store = store
        self._signing_key = signing_key

    def query_investigation(
        self,
        tenant_id: str,
        investigation_id: str,
        *,
        limit: int = 20,
        requesting_tenant_id: str | None = None,
    ) -> list[MemoryEntry]:
        if requesting_tenant_id is not None and requesting_tenant_id != tenant_id:
            return []
        scope = MemoryScope(tenant_id=tenant_id, investigation_id=investigation_id)
        entries = self.store.query(scope, limit=limit)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.MEMORY_TTL_HOURS)
        validator = MemoryEntryValidator(
            namespace_key=f"{tenant_id}:{investigation_id}",
            signing_key=self._signing_key,
        )
        valid: list[MemoryEntry] = []
        for entry in entries:
            if entry.created_at < cutoff:
                continue
            if entry.checksum and not validator.verify_checksum(entry.content, entry.checksum):
                continue
            valid.append(entry)
        valid.sort(key=lambda item: item.trust_score, reverse=True)
        return valid[:limit]

    def list_by_tenant(
        self,
        tenant_id: str,
        *,
        limit: int = 100,
        agent: str | None = None,
        requesting_tenant_id: str | None = None,
    ) -> list[MemoryEntry]:
        if requesting_tenant_id is not None and requesting_tenant_id != tenant_id:
            return []
        list_fn = getattr(self.store, "list_by_tenant", None)
        if list_fn is None:
            return []
        cap = min(max(limit, 1), 200)
        entries = list_fn(tenant_id, limit=cap, agent=agent)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.MEMORY_TTL_HOURS)
        validator_cache: dict[str, MemoryEntryValidator] = {}
        valid: list[MemoryEntry] = []
        for entry in entries:
            if entry.created_at < cutoff:
                continue
            inv_id = entry.scope.investigation_id
            ns = f"{tenant_id}:{inv_id}"
            if ns not in validator_cache:
                validator_cache[ns] = MemoryEntryValidator(namespace_key=ns, signing_key=self._signing_key)
            if entry.checksum and not validator_cache[ns].verify_checksum(entry.content, entry.checksum):
                continue
            valid.append(entry)
        valid.sort(key=lambda item: item.created_at, reverse=True)
        return valid[:cap]

    def format_for_prompt(self, entries: list[MemoryEntry], *, max_chars: int = 4000) -> str:
        if not entries:
            return ""
        lines: list[str] = []
        total = 0
        for entry in entries:
            prefix = "[UNTRUSTED PENDING] " if entry.memory_type == "pending_finding" else ""
            line = (
                f"- {prefix}{entry.source_agent or 'agent'}: {entry.content} "
                f"(type={entry.memory_type}, job={entry.source_job_id})"
            )
            if total + len(line) > max_chars:
                break
            lines.append(line)
            total += len(line)
        return "\n".join(lines)
