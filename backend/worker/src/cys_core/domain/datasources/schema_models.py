from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ModelFamily(str, Enum):
    OPENAI = "openai"
    GENERIC = "generic"


class SchemaExportOptions(BaseModel):
    strict_additional_properties: bool = True
    normalize_required: bool = True


class ModelFamilyKnobs(BaseModel):
    family: ModelFamily = ModelFamily.GENERIC
    strict_additional_properties: bool = False
    normalize_required: bool = True
    reject_unknown_args: bool = False


class SchemaMismatchPayload(BaseModel):
    code: str = "schema_mismatch"
    reason: str = "schema_mismatch"
    tool_name: str = ""
    errors: list[str] = Field(default_factory=list)
