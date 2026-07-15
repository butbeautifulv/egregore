from __future__ import annotations

from pydantic import BaseModel, Field


class QualitySignal(BaseModel):
    name: str
    value: float
    source: str = "eval"
    persona: str = ""
    tool_name: str = ""


class PersonaQuality(BaseModel):
    persona: str
    signals: list[QualitySignal] = Field(default_factory=list)

    def merge_metric(self, name: str, value: float, *, source: str = "eval") -> None:
        self.signals.append(QualitySignal(name=name, value=value, source=source, persona=self.persona))


class ToolQuality(BaseModel):
    tool_name: str
    success_rate: float = 0.0
    stub_rate: float = 0.0
