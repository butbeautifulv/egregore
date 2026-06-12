from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from cys_core.domain.security.a2a import A2A_PROTOCOL_VERSION, A2AEnvelope, default_mtls_subject
from cys_core.domain.security.exceptions import SecurityViolation
from cys_core.domain.security.sanitizer import InputSanitizer


class AgentTrustLevel(int, Enum):
    UNTRUSTED = 0
    INTERNAL = 1
    PRIVILEGED = 2
    SYSTEM = 3


ESCALATION_ONLY_PATHS: set[tuple[str, str]] = {
    ("soc", "redteam"),
    ("network", "redteam"),
}

TRUST_MESSAGE_TYPES: dict[AgentTrustLevel, set[str]] = {
    AgentTrustLevel.UNTRUSTED: {"finding", "query"},
    AgentTrustLevel.INTERNAL: {"finding", "query", "correlation", "escalation"},
    AgentTrustLevel.PRIVILEGED: {"finding", "query", "correlation", "escalation"},
    AgentTrustLevel.SYSTEM: {"finding", "query", "correlation", "escalation", "control"},
}


@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    recovery_timeout: int = 60
    failures: int = 0
    opened_at: float | None = None

    @property
    def is_open(self) -> bool:
        if self.opened_at is None:
            return False
        if time.time() - self.opened_at > self.recovery_timeout:
            self.opened_at = None
            self.failures = 0
            return False
        return True

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.opened_at = time.time()

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None


@dataclass
class SecureAgentBus:
    """Secure inter-agent communication domain service."""

    signing_key: bytes
    sanitizer: InputSanitizer = field(default_factory=InputSanitizer)
    agent_registry: dict[str, dict[str, Any]] = field(default_factory=dict)
    circuit_breakers: dict[str, CircuitBreaker] = field(default_factory=dict)
    security_events: list[dict[str, Any]] = field(default_factory=list)

    def register_agent(
        self,
        agent_id: str,
        trust_level: AgentTrustLevel,
        allowed_recipients: list[str],
        mtls_subject: str | None = None,
    ) -> None:
        self.agent_registry[agent_id] = {
            "trust_level": trust_level,
            "allowed_recipients": allowed_recipients,
            "allowed_message_types": TRUST_MESSAGE_TYPES[trust_level],
            "mtls_subject": mtls_subject or default_mtls_subject(agent_id),
        }
        self.circuit_breakers[agent_id] = CircuitBreaker()

    def send_message(
        self,
        sender_id: str,
        recipient_id: str,
        message_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        sender = self.agent_registry.get(sender_id)
        if not sender:
            raise SecurityViolation(f"Unknown sender agent: {sender_id}")

        breaker = self.circuit_breakers[sender_id]
        if breaker.is_open:
            raise SecurityViolation(f"Agent {sender_id} is temporarily blocked (circuit breaker)")

        if recipient_id not in sender["allowed_recipients"]:
            self._log_security_event(
                "unauthorized_message_attempt",
                {"sender": sender_id, "recipient": recipient_id},
            )
            raise SecurityViolation("Sender not authorized to message recipient")

        if (sender_id, recipient_id) in ESCALATION_ONLY_PATHS:
            if message_type != "escalation" or not payload.get("critic_approved"):
                self._log_security_event(
                    "blocked_privileged_escalation_path",
                    {"sender": sender_id, "recipient": recipient_id, "message_type": message_type},
                )
                raise SecurityViolation(f"Direct path {sender_id}→{recipient_id} requires critic-approved escalation")

        if message_type not in sender["allowed_message_types"]:
            raise SecurityViolation(f"Message type '{message_type}' not allowed")

        sanitized = self._sanitize_payload(payload, sender["trust_level"])
        timestamp = datetime.now(timezone.utc).isoformat()
        signature = self._sign_message(sender_id, recipient_id, message_type, sanitized, timestamp)
        breaker.record_success()
        recipient = self.agent_registry.get(recipient_id, {})
        envelope = A2AEnvelope(
            sender=sender_id,
            recipient=recipient_id,
            type=message_type,
            payload=sanitized,
            timestamp=timestamp,
            signature=signature,
            mtls={
                "required": True,
                "sender_subject": sender["mtls_subject"],
                "recipient_subject": recipient.get("mtls_subject", default_mtls_subject(recipient_id)),
            },
        )
        return envelope.model_dump()

    def receive_message(self, recipient_id: str, message: dict[str, Any]) -> dict[str, Any]:
        if message.get("protocol") != A2A_PROTOCOL_VERSION:
            raise SecurityViolation("Unsupported A2A protocol")
        if not self._verify_signature(message):
            raise SecurityViolation("Invalid message signature")
        msg_time = datetime.fromisoformat(message["timestamp"])
        if datetime.now(timezone.utc) - msg_time > timedelta(minutes=5):
            raise SecurityViolation("Message expired (possible replay attack)")
        if message["recipient"] != recipient_id:
            raise SecurityViolation("Message recipient mismatch")
        recipient = self.agent_registry.get(recipient_id, {})
        expected_subject = recipient.get("mtls_subject", default_mtls_subject(recipient_id))
        if message.get("mtls", {}).get("recipient_subject") != expected_subject:
            raise SecurityViolation("mTLS recipient identity mismatch")
        return message["payload"]

    def record_agent_failure(self, agent_id: str) -> None:
        if agent_id in self.circuit_breakers:
            self.circuit_breakers[agent_id].record_failure()

    def _sanitize_payload(self, payload: dict[str, Any], trust_level: AgentTrustLevel) -> dict[str, Any]:
        if trust_level < AgentTrustLevel.PRIVILEGED:
            payload = {k: v for k, v in payload.items() if not str(k).startswith("_system")}
        result: dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, str):
                result[key] = self.sanitizer.filter_untrusted(value, source="agent_bus")
            else:
                result[key] = value
        return result

    def _sign_message(
        self,
        sender: str,
        recipient: str,
        message_type: str,
        payload: dict[str, Any],
        timestamp: str,
    ) -> str:
        body = json.dumps(
            {
                "sender": sender,
                "recipient": recipient,
                "type": message_type,
                "payload": payload,
                "timestamp": timestamp,
            },
            sort_keys=True,
        )
        return hmac.new(self.signing_key, body.encode(), hashlib.sha256).hexdigest()

    def _verify_signature(self, message: dict[str, Any]) -> bool:
        expected = self._sign_message(
            message["sender"],
            message["recipient"],
            message["type"],
            message["payload"],
            message["timestamp"],
        )
        return hmac.compare_digest(expected, message.get("signature", ""))

    def _log_security_event(self, event_type: str, details: dict[str, Any]) -> None:
        self.security_events.append({"type": event_type, "details": details, "ts": time.time()})
