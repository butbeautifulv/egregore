from __future__ import annotations

from typing import Protocol

from cys_core.domain.observability.models import JudgeRequest, JudgeResult


class JudgeBackendPort(Protocol):
    def judge(self, request: JudgeRequest) -> JudgeResult: ...
