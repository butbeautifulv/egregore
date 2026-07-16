from __future__ import annotations

from bootstrap.settings import get_settings
from cys_core.application.ports.application_settings import ApplicationSettingsPort


class BootstrapApplicationSettingsAdapter:
    def reasoning_model_configured(self) -> bool:
        return bool(get_settings().reasoning_model.strip())

    def e2b_api_key_configured(self) -> bool:
        return bool(get_settings().e2b_api_key.strip())


def build_application_settings_port() -> ApplicationSettingsPort:
    return BootstrapApplicationSettingsAdapter()
