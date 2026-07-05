from __future__ import annotations

import structlog

from bootstrap.container import get_container
from cys_core.observability.tracing import bind_correlation_id, reset_correlation_id
from interfaces.control_plane.critic_service import get_critic_service

logger = structlog.get_logger(__name__)


class CriticHandler:
    async def handle(self, envelope: dict) -> None:
        payload = envelope.get("payload", {})
        investigation_id = str(payload.get("correlation_id", payload.get("event_id", "")))
        tenant_id = str(payload.get("tenant_id", "default"))
        token = bind_correlation_id(investigation_id) if investigation_id else None
        try:
            await get_critic_service().handle_message(envelope)
        except Exception as exc:
            logger.exception("control_handler_failed", recipient="critic", engagement_id=investigation_id)
            if investigation_id:
                get_container().get_engagement_egress().publish_event(
                    investigation_id,
                    "control_error",
                    {
                        "error": str(exc),
                        "recipient": "critic",
                        "job_id": f"critic:{investigation_id}",
                        "tenant_id": tenant_id,
                    },
                )
            raise
        finally:
            if token is not None:
                reset_correlation_id(token)
