from __future__ import annotations

from typing import Protocol


class ApplicationSettingsPort(Protocol):
    def reasoning_model_configured(self) -> bool: ...

    def e2b_api_key_configured(self) -> bool: ...
