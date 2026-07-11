from __future__ import annotations

from cys_core.domain.policy.defaults import DEFAULT_PROFILE_ID, default_profile_policy_payload


def default_profile_policy():
    return default_profile_policy_payload()


def default_profile_pack(*, id: str, default_personas: list[str]):
    from cys_core.domain.catalog.models import PlannerPack, ProfilePack
    from cys_core.registry.product_context import get_product_context

    product = get_product_context()
    return ProfilePack(
        id=id,
        name="Cybersec SOC" if id == DEFAULT_PROFILE_ID else id,
        description="Filesystem seed profile",
        default_personas=default_personas,
        default_plan=product.manifest.default_plan,
        global_rules=product.rules_block,
        policy=default_profile_policy(),
        planner=PlannerPack(
            post_processors=["advisory_consultant_fallback", "staged_soc_intel_for_incident"],
            synthesis_default="consultant",
        ),
        intake_schema={
            "type": "object",
            "properties": {
                "goal": {"type": "string"},
                "incident_id": {"type": "string"},
                "alert_ids": {"type": "array", "items": {"type": "string"}},
                "iocs": {"type": "array", "items": {"type": "string"}},
                "log_refs": {"type": "array", "items": {"type": "string"}},
                "context": {"type": "object"},
            },
        },
    )
