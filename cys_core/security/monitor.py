from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import structlog

logger = structlog.get_logger()


@dataclass
class AgentSecurityEvent:
    event_type: str
    severity: str
    agent_id: str
    session_id: str
    user_id: str
    timestamp: datetime
    details: dict[str, Any]
    tool_name: str | None = None


class AgentMonitor:
    """Log and detect anomalous agent behavior (cheat sheet §6)."""

    ANOMALY_THRESHOLDS = {
        "tool_calls_per_minute": 30,
        "failed_tool_calls": 5,
        "injection_attempts": 1,
        "sensitive_data_access": 3,
    }

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.session_metrics: dict[str, dict[str, Any]] = {}
        self.events: list[AgentSecurityEvent] = []

    def log_tool_call(
        self,
        session_id: str,
        tool_name: str,
        params: dict[str, Any],
        result: dict[str, Any],
        user_id: str = "system",
    ) -> None:
        event = AgentSecurityEvent(
            event_type="tool_call",
            severity="INFO",
            agent_id=self.agent_id,
            session_id=session_id,
            user_id=user_id,
            timestamp=datetime.now(timezone.utc),
            tool_name=tool_name,
            details={
                "parameters": self._redact_sensitive(params),
                "result_status": result.get("status", "ok"),
            },
        )
        self._emit(event)
        self._check_anomalies(session_id, event)

    def log_security_event(
        self,
        session_id: str,
        event_type: str,
        severity: str,
        details: dict[str, Any],
        user_id: str = "system",
    ) -> None:
        event = AgentSecurityEvent(
            event_type=event_type,
            severity=severity,
            agent_id=self.agent_id,
            session_id=session_id,
            user_id=user_id,
            timestamp=datetime.now(timezone.utc),
            details=details,
        )
        self._emit(event)

    def _emit(self, event: AgentSecurityEvent) -> None:
        self.events.append(event)
        logger.info(
            "agent_security_event",
            event_type=event.event_type,
            severity=event.severity,
            agent_id=event.agent_id,
            session_id=event.session_id,
            tool_name=event.tool_name,
            details=event.details,
        )

    def _check_anomalies(self, session_id: str, event: AgentSecurityEvent) -> None:
        metrics = self.session_metrics.setdefault(
            session_id, {"tool_calls": [], "failed_calls": 0}
        )
        metrics["tool_calls"].append(datetime.now(timezone.utc))
        recent = [
            t
            for t in metrics["tool_calls"]
            if (datetime.now(timezone.utc) - t).total_seconds() < 60
        ]
        if len(recent) > self.ANOMALY_THRESHOLDS["tool_calls_per_minute"]:
            self.log_security_event(
                session_id,
                "anomaly_detected",
                "WARNING",
                {"reason": "excessive_tool_calls", "count": len(recent)},
                event.user_id,
            )

    def _redact_sensitive(self, data: Any) -> Any:
        sensitive_keys = {"password", "api_key", "token", "secret", "credential"}
        if isinstance(data, dict):
            return {
                k: "***REDACTED***" if k.lower() in sensitive_keys else self._redact_sensitive(v)
                for k, v in data.items()
            }
        if isinstance(data, list):
            return [self._redact_sensitive(i) for i in data]
        return data
