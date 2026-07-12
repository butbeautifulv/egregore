"""Product pack seed definitions (Stream D1)."""

from __future__ import annotations

from cys_core.domain.catalog.product_packs import (
    DomainPack,
    EvalPack,
    PersonaPack,
    ProductProfilePack,
)
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID

CYBERSEC_SOC_PRODUCT = ProductProfilePack(
    id="cybersec-soc",
    name="Cybersec SOC",
    description="Default cybersecurity operations product",
    profile_id=DEFAULT_PROFILE_ID,
    seed_module="bootstrap.catalog_loader.load_profile_pack",
    domains=[
        DomainPack(
            id="cybersecurity",
            name="Cybersecurity",
            default_plan="incident-triage",
            routing_event_types=["siem.alert", "engagement.start"],
        )
    ],
    personas=[
        PersonaPack(id="consultant", name="Consultant", catalog_agent="consultant"),
        PersonaPack(id="soc", name="SOC Analyst", catalog_agent="soc"),
    ],
    eval_pack=EvalPack(id="soc-eval", suite="trace-critic", metrics=["faithfulness", "tool_success"]),
)

GENERAL_ASSISTANT_PRODUCT = ProductProfilePack(
    id="general-assistant",
    name="General Assistant",
    description="Minimal general-purpose assistant pack",
    profile_id="general-assistant",
    domains=[DomainPack(id="general", name="General", default_plan="consultation")],
    personas=[PersonaPack(id="assistant", name="Assistant", catalog_agent="consultant")],
)

GAIA_BENCHMARK_PRODUCT = ProductProfilePack(
    id="gaia-benchmark",
    name="GAIA Benchmark",
    description="Isolated benchmark pack without SOC policy defaults",
    profile_id="gaia-benchmark",
    domains=[DomainPack(id="benchmark", name="Benchmark", default_plan="full-assessment")],
    personas=[PersonaPack(id="gaia_solver", name="GAIA Solver", catalog_agent="gaia_solver")],
    eval_pack=EvalPack(id="gaia-eval", suite="gaia", benchmark_profile="gaia-benchmark"),
)

PRODUCT_PACKS: dict[str, ProductProfilePack] = {
    CYBERSEC_SOC_PRODUCT.id: CYBERSEC_SOC_PRODUCT,
    GENERAL_ASSISTANT_PRODUCT.id: GENERAL_ASSISTANT_PRODUCT,
    GAIA_BENCHMARK_PRODUCT.id: GAIA_BENCHMARK_PRODUCT,
}


def product_pack_to_profile_pack(pack: ProductProfilePack):
    from bootstrap.policy_defaults import default_profile_pack
    from cys_core.domain.catalog.models import PlannerPack

    mode = "off" if pack.id == "general-assistant" else "gate_only"
    if pack.id == "gaia-benchmark":
        mode = "full"
    profile = default_profile_pack(
        id=pack.profile_id,
        default_personas=[p.catalog_agent for p in pack.personas if p.enabled],
        control_plane_mode=mode,
    )
    if pack.id == "general-assistant":
        profile.planner = PlannerPack(
            post_processors=["advisory_consultant_fallback"],
            synthesis_default="consultant",
        )
    return profile
