from __future__ import annotations

from cys_core.application.adapters.security_event_adapter import security_event_to_domain
from cys_core.application.ports.product_pack import ProductPackPort
from cys_core.application.routing.event_router import EventRouter
from cys_core.domain.catalog.profile_id import resolve_profile_id
from cys_core.domain.events.domain_events import DomainEvent
from cys_core.domain.events.models import RoutingDecision, SecurityEvent


def resolve_domain_for_profile(profile_id: str, *, packs: ProductPackPort) -> str:
    return packs.default_domain_for_profile(profile_id)


def route_security_via_domain_adapter(
    router: EventRouter,
    event: SecurityEvent,
    *,
    packs: ProductPackPort,
) -> RoutingDecision:
    """Map SecurityEvent → DomainEvent using product pack domain, then route."""
    profile_id = resolve_profile_id(payload=event.payload)
    domain = resolve_domain_for_profile(profile_id, packs=packs)
    domain_event = security_event_to_domain(event, domain=domain)
    return router.route(_domain_to_security(domain_event))


def _domain_to_security(event: DomainEvent) -> SecurityEvent:
    from cys_core.domain.events.models import SecurityEvent as Sec

    return Sec(
        id=event.id,
        type=event.event_type,  # type: ignore[arg-type]
        source=event.source,
        severity=event.severity,
        payload={**event.payload, "profile_id": event.profile_id, "domain": event.domain},
        tenant_id=event.tenant_id,
        correlation_id=event.correlation_id,
    )
