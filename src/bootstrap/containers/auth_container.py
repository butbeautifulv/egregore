from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bootstrap.container import Container


class AuthContainer:
    """Owns token verification and authz service/port construction."""

    def __init__(self, container: "Container") -> None:
        self._container = container
        self._authz_port = None
        self._authz_service = None

    @property
    def settings(self):
        return self._container.settings

    def get_token_verifier(self):
        from cys_core.infrastructure.auth.factory import build_token_verifier

        return build_token_verifier(self.settings)

    def get_authz_service(self):
        if self._authz_service is not None:
            return self._authz_service
        from cys_core.application.authz.audit import log_authz_deny
        from cys_core.application.authz.service import AuthzService
        from cys_core.observability.authz_trace import record_authz_decision
        from cys_core.observability.metrics import metrics

        self._authz_service = AuthzService(
            self.get_authz_port(),
            mode=self.settings.authz_mode,
            metrics=metrics,
            record_decision=lambda decision, relation, object: record_authz_decision(
                decision, relation=relation, object=object
            ),
            log_deny=log_authz_deny,
        )
        return self._authz_service

    def get_authz_port(self):
        if self._authz_port is not None:
            return self._authz_port
        settings = self.settings
        if settings.authz_mode != "off" and settings.openfga_api_url.strip() and settings.openfga_store_id.strip():
            from cys_core.infrastructure.authz.openfga import OpenFgaAuthzPort

            self._authz_port = OpenFgaAuthzPort(
                api_url=settings.openfga_api_url,
                store_id=settings.openfga_store_id,
                api_token=settings.openfga_api_token,
                model_id=settings.openfga_model_id,
            )
        else:
            from cys_core.infrastructure.authz.noop import NoopAuthzPort

            self._authz_port = NoopAuthzPort()
        return self._authz_port
