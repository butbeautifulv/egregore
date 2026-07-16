from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from cys_core.domain.catalog.models import AgentCatalogEntry
from cys_core.domain.policy.defaults import PERSONA_CLEARANCE
from cys_core.domain.policy.pure import persona_clearance_pure
from cys_core.domain.security.data_classification import DataClassification

_CLASS_ORDER = [
    DataClassification.PUBLIC,
    DataClassification.INTERNAL,
    DataClassification.CONFIDENTIAL,
    DataClassification.RESTRICTED,
]


def persona_clearance_for(persona: str, entry: AgentCatalogEntry | None = None) -> DataClassification:
    return persona_clearance_pure(persona, entry)


class SecureContextBuilder(BaseModel):
    """Classify data and apply protection rules per operation."""

    persona: str = ""
    tenant: str = "default"
    roles: list[str] = Field(default_factory=list)

    def persona_clearance(self) -> DataClassification:
        return persona_clearance_for(self.persona)

    def classify_text(self, text: str) -> DataClassification:
        lower = text.lower()
        if any(k in lower for k in ("ssn", "passport", "credit card", "паспорт")):
            return DataClassification.RESTRICTED
        if any(k in lower for k in ("password", "api_key", "secret", "token")):
            return DataClassification.CONFIDENTIAL
        if any(k in lower for k in ("internal only", "confidential")):
            return DataClassification.CONFIDENTIAL
        return DataClassification.INTERNAL

    def can_access(self, classification: DataClassification) -> bool:
        return _CLASS_ORDER.index(classification) <= _CLASS_ORDER.index(self.persona_clearance())

    def include_in_context(self, classification: DataClassification) -> bool:
        if classification == DataClassification.RESTRICTED:
            return self.persona_clearance() == DataClassification.RESTRICTED
        return self.can_access(classification)

    def redact_for_output(self, text: str, classification: DataClassification) -> str:
        if self.include_in_context(classification):
            return text
        return "[REDACTED_CLASSIFICATION]"

    def log_allowed(self, classification: DataClassification) -> bool:
        return classification != DataClassification.RESTRICTED

    def apply_protection(self, payload: dict[str, Any]) -> dict[str, Any]:
        classification = DataClassification(payload.get("classification", DataClassification.INTERNAL))
        text = str(payload.get("text", ""))
        if not self.include_in_context(classification):
            return {**payload, "text": self.redact_for_output(text, classification), "redacted": True}
        return payload


__all__ = ["PERSONA_CLEARANCE", "DataClassification", "SecureContextBuilder", "persona_clearance_for"]
