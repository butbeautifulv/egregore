from __future__ import annotations

from langchain_core.tools import StructuredTool

from interfaces.gateways.skill.load import SkillLoadError, load_skill


def make_load_skill_tool(
    allowed_skills: list[str],
    *,
    persona: str,
    job_id: str = "",
) -> StructuredTool:
    def _run(skill_name: str) -> str:
        try:
            return load_skill(skill_name, persona=persona, allowed_skills=allowed_skills, job_id=job_id)
        except SkillLoadError as exc:
            return f"SKILL_LOAD_ERROR: {exc}"

    return StructuredTool.from_function(
        func=_run,
        name="load_skill",
        description="Load an allowlisted skill playbook body on demand (via Skill Gateway).",
    )
