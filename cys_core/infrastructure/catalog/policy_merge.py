from __future__ import annotations

import structlog

from cys_core.domain.catalog.models import ProfilePack, ProfilePolicyPayload

logger = structlog.get_logger(__name__)


def merge_profile_policy(existing: ProfilePolicyPayload, patch: dict) -> ProfilePolicyPayload:
    data = existing.model_dump()
    for key, value in patch.items():
        if value is None:
            continue
        if key == "tool_allowlist" and isinstance(value, dict):
            merged = dict(data.get("tool_allowlist") or {})
            merged.update(value)
            data["tool_allowlist"] = merged
        elif key == "tool_risk" and isinstance(value, dict):
            merged = dict(data.get("tool_risk") or {})
            merged.update(value)
            data["tool_risk"] = merged
        elif key == "mode_policy" and isinstance(value, dict):
            merged = dict(data.get("mode_policy") or {})
            for sub_key, sub_val in value.items():
                if isinstance(sub_val, list):
                    existing_list = list(merged.get(sub_key) or [])
                    merged[sub_key] = sorted(set(existing_list) | set(sub_val))
                else:
                    merged[sub_key] = sub_val
            data["mode_policy"] = merged
        elif key in ("trace_critic", "anomaly", "quality_signals") and isinstance(value, dict):
            nested = dict(data.get(key) or {})
            nested.update(value)
            data[key] = nested
        else:
            data[key] = value
    return ProfilePolicyPayload.model_validate(data)


def merge_profile_pack(existing: ProfilePack | None, *, profile_id: str, body: dict) -> ProfilePack:
    if "global_rules" in body:
        logger.warning("profile_pack_global_rules_ignored", profile_id=profile_id)
    if existing is None:
        return ProfilePack(
            id=profile_id,
            name=body.get("name", profile_id),
            description=body.get("description", ""),
            default_personas=body.get("default_personas", []),
            default_skills=body.get("default_skills", []),
            policy=ProfilePolicyPayload.model_validate(body.get("policy") or {}),
        )
    policy_patch = body.get("policy")
    policy = (
        merge_profile_policy(existing.policy, policy_patch)
        if isinstance(policy_patch, dict)
        else existing.policy
    )
    return ProfilePack(
        id=profile_id,
        name=body.get("name", existing.name),
        description=body.get("description", existing.description),
        default_personas=body.get("default_personas", existing.default_personas),
        default_skills=body.get("default_skills", existing.default_skills),
        default_plan=body.get("default_plan", existing.default_plan),
        global_rules="",
        hints_template=body.get("hints_template", existing.hints_template),
        policy=policy,
    )
