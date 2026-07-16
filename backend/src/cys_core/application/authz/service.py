"""Authz service with AUTHZ_MODE=off|shadow|enforce."""

from __future__ import annotations

import time
from collections.abc import Callable
from enum import StrEnum
from typing import Literal

import structlog

from cys_core.application.ports.authz import AuthzCheck, AuthzPort, AuthzTuple

logger = structlog.get_logger(__name__)

AuthzMode = Literal["off", "shadow", "enforce"]

RecordDecisionFn = Callable[[str, str, str], None]
LogDenyFn = Callable[..., None]


class AuthzDenied(Exception):
    def __init__(self, *, user: str, relation: str, object: str) -> None:
        self.user = user
        self.relation = relation
        self.object = object
        super().__init__(f"authz_denied user={user} relation={relation} object={object}")


class AuthzModeSetting(StrEnum):
    OFF = "off"
    SHADOW = "shadow"
    ENFORCE = "enforce"


class AuthzService:
    def __init__(
        self,
        port: AuthzPort,
        *,
        mode: AuthzMode = "off",
        metrics=None,
        record_decision: RecordDecisionFn | None = None,
        log_deny: LogDenyFn | None = None,
    ) -> None:
        self._port = port
        self.mode = mode
        self._metrics = metrics
        self._record_decision = record_decision
        self._log_deny = log_deny

    def check(self, user: str, relation: str, object: str) -> bool:
        if self.mode == "off":
            return True
        start = time.perf_counter()
        allowed = False
        error = False
        try:
            allowed = self._port.check(AuthzCheck(user=user, relation=relation, object=object))
        except Exception as exc:
            error = True
            logger.warning("authz_check_error", error=str(exc), user=user, relation=relation, object=object)
            if self.mode == "enforce":
                self._observe(relation=relation, object=object, decision="error", start=start)
                raise AuthzDenied(user=user, relation=relation, object=object) from exc
            allowed = True
        decision = "allow" if allowed else "deny"
        if self._record_decision is not None:
            self._record_decision(decision, relation, object)
        self._observe(relation=relation, object=object, decision="error" if error else decision, start=start)
        if self.mode == "shadow":
            logger.info(
                "authz_shadow",
                user=user,
                relation=relation,
                object=object,
                allowed=allowed,
            )
            return True
        if not allowed:
            logger.info("authz_deny", user=user, relation=relation, object=object)
            if self._log_deny is not None:
                self._log_deny(user=user, relation=relation, object=object)
            raise AuthzDenied(user=user, relation=relation, object=object)
        return True

    def list_objects(self, *, user: str, relation: str, object_type: str) -> list[str]:
        if self.mode == "off":
            return []
        try:
            return self._port.list_objects(user=user, relation=relation, object_type=object_type)
        except Exception as exc:
            logger.warning("authz_list_objects_error", error=str(exc))
            if self.mode == "enforce":
                raise
            return []

    def write_tuples(self, tuples: list[AuthzTuple]) -> None:
        if self.mode == "off":
            return
        self._port.write_tuples(tuples)

    def delete_tuples(self, tuples: list[AuthzTuple]) -> None:
        if self.mode == "off":
            return
        self._port.delete_tuples(tuples)

    def ping(self) -> bool:
        if self.mode == "off":
            return True
        try:
            return self._port.ping()
        except Exception:
            return False

    def _observe(self, *, relation: str, object: str, decision: str, start: float) -> None:
        if self._metrics is None:
            return
        object_type = object.split(":", 1)[0] if ":" in object else object
        try:
            self._metrics.authz_check_total.labels(
                decision=decision,
                relation=relation,
                object_type=object_type,
            ).inc()
            if decision == "deny":
                self._metrics.authz_deny_total.labels(relation=relation, object_type=object_type).inc()
            if decision == "error":
                self._metrics.authz_error_total.labels(relation=relation, object_type=object_type).inc()
            self._metrics.authz_check_latency.labels(relation=relation).observe(time.perf_counter() - start)
        except Exception:
            pass
