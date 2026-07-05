from __future__ import annotations

import hashlib
import json

import structlog
from langchain_core.tools import StructuredTool

from cys_core.infrastructure.skill.load_skill import SkillLoadError, load_skill
from cys_core.observability.metrics import metrics

logger = structlog.get_logger(__name__)


def _parse_skill_name_from_inputs(inputs: dict | None, input_str: str) -> str:
    if isinstance(inputs, dict):
        for key in ("skill_name", "name", "skill"):
            value = inputs.get(key)
            if value:
                return str(value)
    text = (input_str or "").strip()
    if text.startswith("{"):
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                return _parse_skill_name_from_inputs(payload, "")
        except json.JSONDecodeError:
            pass
    return text


def _emit_skill_loaded(
    *,
    skill_name: str,
    persona: str,
    job_id: str,
    investigation_id: str,
    tenant_id: str,
    body: str,
) -> None:
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]
    logger.info(
        "skill_loaded",
        skill_name=skill_name,
        persona=persona,
        job_id=job_id,
        engagement_id=investigation_id,
        content_digest=digest,
    )
    metrics.record_skill_load(skill_name, persona)
    if not investigation_id:
        return
    try:
        from cys_core.infrastructure.engagement.factory import get_engagement_egress

        get_engagement_egress().publish_event(
            investigation_id,
            "skill_loaded",
            {
                "tenant_id": tenant_id,
                "skill_name": skill_name,
                "persona": persona,
                "job_id": job_id,
                "content_digest": digest,
            },
        )
    except Exception:
        pass


def make_load_skill_tool(
    allowed_skills: list[str],
    *,
    persona: str,
    job_id: str = "",
    investigation_id: str = "",
    tenant_id: str = "default",
) -> StructuredTool:
    def _run(skill_name: str) -> str:
        try:
            body = load_skill(skill_name, persona=persona, allowed_skills=allowed_skills, job_id=job_id)
            _emit_skill_loaded(
                skill_name=skill_name,
                persona=persona,
                job_id=job_id,
                investigation_id=investigation_id,
                tenant_id=tenant_id,
                body=body,
            )
            return body
        except SkillLoadError as exc:
            return f"SKILL_LOAD_ERROR: {exc}"

    return StructuredTool.from_function(
        func=_run,
        name="load_skill",
        description="Load an allowlisted skill playbook body on demand (via Skill Gateway).",
    )
