from __future__ import annotations

from bootstrap.container import get_container
from cys_core.infrastructure.control.control_narrator import LlmControlNarrator, TemplateControlNarrator


def get_control_narrator():
    container = get_container()
    from cys_core.application.use_cases.narrate_investigation import NarrateInvestigationProgress

    narrate_use_case = NarrateInvestigationProgress(
        runtime=None,
        engagement_store=container.get_engagement_state_store(),
        memory_reader=container.get_memory_read_service(),
        application_tracing=container.get_application_tracing_port(),
    )

    async def _narrate(**kwargs):
        return await narrate_use_case.execute(**kwargs)

    if container.settings.coordinator_llm_narrative:
        llm_case = NarrateInvestigationProgress(
            runtime=container.get_agent_runtime(),
            engagement_store=container.get_engagement_state_store(),
            memory_reader=container.get_memory_read_service(),
            application_tracing=container.get_application_tracing_port(),
        )

        async def _llm_narrate(**kwargs):
            return await llm_case.execute(**kwargs)

        return LlmControlNarrator(narrate_fn=_llm_narrate)
    return TemplateControlNarrator(narrate_fn=_narrate)
