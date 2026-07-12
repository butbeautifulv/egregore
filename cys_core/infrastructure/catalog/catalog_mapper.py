from __future__ import annotations

from typing import Literal, cast

from cys_core.domain.agents.models import AgentDefinition
from cys_core.domain.catalog.models import AgentCatalogEntry, CatalogSource
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.domain.security.system_prompt_assembler import (
    assemble_trusted_system_context,
    resolve_persona_prompt,
)


def entry_to_definition(entry: AgentCatalogEntry) -> AgentDefinition:
    persona = resolve_persona_prompt(entry)
    ctx = assemble_trusted_system_context(persona, language=entry.language)
    return AgentDefinition(
        name=entry.name,
        description=entry.description,
        role=cast(Literal["worker", "control", "specialist", "critic", "coordinator"], entry.role),
        system_prompt=ctx.text,
        system_prompt_digest=ctx.digest,
        schema_name=entry.output_schema,
        tools=entry.tools,
        skills=entry.skills,
        hitl_tools=entry.hitl_tools,
        trust_level=entry.trust_level,
        bus_recipients=entry.bus_recipients,
        capabilities=entry.capabilities,
        persona_prompt=persona,
        language=entry.language,
    )


def definition_to_entry(defn: AgentDefinition, *, profile_id: str = DEFAULT_PROFILE_ID) -> AgentCatalogEntry:
    from cys_core.domain.security.classification import persona_clearance_for
    from cys_core.domain.security.system_prompt_assembler import extract_persona_prompt
    from cys_core.domain.workers.budgets import persona_budget

    budget = persona_budget(defn.name)
    persona_prompt = defn.persona_prompt or extract_persona_prompt(defn.system_prompt)
    return AgentCatalogEntry(
        name=defn.name,
        description=defn.description,
        role=defn.role,
        output_schema=defn.schema_name,
        tools=defn.tools,
        skills=defn.skills,
        hitl_tools=defn.hitl_tools,
        trust_level=defn.trust_level,
        bus_recipients=defn.bus_recipients,
        persona_prompt=persona_prompt,
        language=defn.language,
        system_prompt="",
        system_prompt_digest=defn.system_prompt_digest,
        profile_id=profile_id,
        source=CatalogSource.FILESYSTEM,
        enabled=True,
        capabilities=defn.capabilities,
        budget_max_tokens=budget.max_tokens,
        budget_max_cost_usd=budget.max_cost_usd,
        budget_max_tool_calls=budget.max_tool_calls,
        data_clearance=persona_clearance_for(defn.name).value,
    )
