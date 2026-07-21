from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from enum import IntEnum
from typing import Any

from cys_core.domain.catalog.models import ProfilePolicyPayload
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.domain.policy.defaults import DEFAULT_BUS_POLICY, ESCALATION_ONLY_PATHS, default_profile_policy_payload
from cys_core.domain.security.a2a import A2A_PROTOCOL_VERSION, default_mtls_subject
from cys_core.domain.security.exceptions import SecurityViolation
from cys_core.domain.security.sanitizer import InputSanitizer

_STRUCTURAL_ID_KEYS = frozenset(
    {
        "correlation_id",
        "event_id",
        "investigation_id",
        "engagement_id",
        "tenant_id",
        "job_id",
        "message_id",
        "parent_correlation_key",
    }
)


class AgentTrustLevel(IntEnum):
    UNTRUSTED = 0
    INTERNAL = 1
    PRIVILEGED = 2
    SYSTEM = 3


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.opened_at = 0.0

    @property
    def is_open(self) -> bool:
        if self.failures < self.failure_threshold:
            return False
        if time.time() - self.opened_at >= self.recovery_timeout:
            self.failures = 0
            self.opened_at = 0.0
            return False
        return True

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.opened_at = time.time()

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = 0.0


class SecureAgentBus:
    """Signed A2A bus with trust levels, escalation gates, and circuit breakers."""

    def __init__(
        self,
        signing_key: bytes | str = b"cys-agi-bus-key",
        *,
        profile_id: str = DEFAULT_PROFILE_ID,
        policy: ProfilePolicyPayload | None = None,
    ) -> None:
        self.signing_key = signing_key if isinstance(signing_key, bytes) else signing_key.encode("utf-8")
        self.profile_id = profile_id
        self.agent_registry: dict[str, dict[str, Any]] = {}
        self.circuit_breakers: dict[str, CircuitBreaker] = {}
        self.security_events: list[dict[str, Any]] = []
        self._sanitizer = InputSanitizer()
        self._apply_policy(policy or default_profile_policy_payload())

    def _apply_policy(self, policy: ProfilePolicyPayload) -> None:
        self._breaker_threshold = policy.breaker_failure_threshold
        self._breaker_reset = policy.breaker_reset_seconds
        self._bus_policy = dict(policy.bus_policy) if policy.bus_policy else dict(DEFAULT_BUS_POLICY)
        if policy.escalation_paths:
            self._escalation_paths: set[tuple[str, str]] = {
                (pair[0], pair[1]) for pair in policy.escalation_paths if len(pair) == 2
            }
        else:
            self._escalation_paths = set(ESCALATION_ONLY_PATHS)

    @property
    def escalation_paths(self) -> set[tuple[str, str]]:
        """This bus's active profile's escalation pairs — resolved once in `_apply_policy`
        from `ProfilePolicyPayload.escalation_paths`, falling back to the cybersec-soc
        `ESCALATION_ONLY_PATHS` constant only when the policy doesn't set any. Exposed so
        callers like `filter_escalation_recipients` (docs/MSP_BACKLOG.md §8.4 point 3) use
        the same profile-resolved value this bus already computed, instead of re-importing
        the hardcoded constant directly."""
        return set(self._escalation_paths)

    def register_agent(
        self,
        agent_id: str,
        trust_level: AgentTrustLevel,
        allowed_recipients: list[str],
    ) -> None:
        self.agent_registry[agent_id] = {
            "trust_level": trust_level,
            "allowed_recipients": list(allowed_recipients),
            "allowed_message_types": self._allowed_types(trust_level),
        }
        self.circuit_breakers[agent_id] = CircuitBreaker(
            failure_threshold=self._breaker_threshold,
            recovery_timeout=self._breaker_reset,
        )

    def record_agent_failure(self, agent_id: str) -> None:
        breaker = self.circuit_breakers.get(agent_id)
        if breaker is not None:
            breaker.record_failure()

    def send_message(
        self,
        sender: str,
        recipient: str,
        message_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        sender_info = self.agent_registry.get(sender)
        if sender_info is None:
            raise SecurityViolation(f"Unknown sender agent: {sender}")

        breaker = self.circuit_breakers.get(sender)
        if breaker is not None and breaker.is_open:
            raise SecurityViolation(f"Agent {sender} circuit breaker open")

        if recipient not in sender_info["allowed_recipients"]:
            self._log_event("unauthorized_message_attempt", {"sender": sender, "recipient": recipient})
            raise SecurityViolation(f"Sender {sender} not authorized to message {recipient}")

        if message_type not in sender_info["allowed_message_types"]:
            raise SecurityViolation(f"Message type '{message_type}' not allowed for {sender}")

        if (sender, recipient) in self._escalation_paths:
            if message_type != "escalation" or not payload.get("critic_approved"):
                self._log_event(
                    "blocked_privileged_escalation_path",
                    {"sender": sender, "recipient": recipient, "type": message_type},
                )
                raise SecurityViolation("Privileged escalation requires critic-approved escalation message")

        sanitized = self._sanitize_payload(payload, sender_info["trust_level"])
        timestamp = datetime.now(timezone.utc).isoformat()
        signature = self._sign_message(sender, recipient, message_type, sanitized, timestamp)
        return {
            "protocol": A2A_PROTOCOL_VERSION,
            "sender": sender,
            "recipient": recipient,
            "type": message_type,
            "payload": sanitized,
            "timestamp": timestamp,
            "signature": signature,
            "mtls": {
                "required": True,
                "sender_subject": default_mtls_subject(sender),
                "recipient_subject": default_mtls_subject(recipient),
            },
        }

    def receive_message(self, recipient: str, message: dict[str, Any]) -> dict[str, Any]:
        if message.get("protocol") != A2A_PROTOCOL_VERSION:
            raise SecurityViolation("Unsupported A2A protocol version")
        if message.get("recipient") != recipient:
            raise SecurityViolation("Message recipient mismatch")
        expected = self._sign_message(
            message["sender"],
            message["recipient"],
            message["type"],
            message["payload"],
            message["timestamp"],
        )
        if not hmac.compare_digest(message.get("signature", ""), expected):
            raise SecurityViolation("Invalid message signature")
        msg_time = datetime.fromisoformat(message["timestamp"])
        if datetime.now(timezone.utc) - msg_time > timedelta(minutes=5):
            raise SecurityViolation("Message expired (possible replay attack)")
        mtls = message.get("mtls", {})
        if mtls.get("recipient_subject") != default_mtls_subject(recipient):
            raise SecurityViolation("mTLS recipient identity mismatch")
        return message["payload"]

    def _allowed_types(self, trust_level: AgentTrustLevel) -> list[str]:
        if trust_level <= AgentTrustLevel.UNTRUSTED:
            return ["finding"]
        if trust_level >= AgentTrustLevel.PRIVILEGED:
            return ["finding", "escalation", "control", "report", "revision", "delegate"]
        return ["finding", "escalation", "delegate"]

    def _sanitize_payload(self, payload: dict[str, Any], trust_level: AgentTrustLevel) -> dict[str, Any]:
        cleaned = dict(payload)
        if trust_level < AgentTrustLevel.PRIVILEGED:
            cleaned = {key: value for key, value in cleaned.items() if not str(key).startswith("_system")}
        result: dict[str, Any] = {}
        for key, value in cleaned.items():
            if isinstance(value, str):
                if key in _STRUCTURAL_ID_KEYS:
                    result[key] = value
                else:
                    result[key] = self._sanitizer.filter_untrusted(value, source="agent_bus")
            elif isinstance(value, dict):
                result[key] = self._sanitize_payload(value, trust_level)
            elif isinstance(value, list):
                result[key] = [
                    self._sanitizer.filter_untrusted(item, source="agent_bus") if isinstance(item, str) else item
                    for item in value
                ]
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
            separators=(",", ":"),
        )
        return hmac.new(self.signing_key, body.encode("utf-8"), hashlib.sha256).hexdigest()

    def _log_event(self, event_type: str, details: dict[str, Any]) -> None:
        self.security_events.append(
            {
                "type": event_type,
                "details": details,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        )
