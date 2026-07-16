from __future__ import annotations

import re

from cys_core.domain.evidence.models import EvidenceManifest, EvidenceRef, Observation
from cys_core.domain.evidence.observation_ids import parse_obs_id, slug_observation_value

_PROCESS_ENTITY = re.compile(r"\b([A-Za-z0-9_.-]+\.exe)\b", re.I)
_PID_ENTITY = re.compile(r"\bpid\s*[:=]?\s*(\d+)\b", re.I)
_PIPE_ENTITY = re.compile(r"(\\\\\.\\pipe\\[^\s\"']+|pipe\\[^\s\"']+)", re.I)
_ACCOUNT_ENTITY = re.compile(r"\b([A-Za-z0-9_.-]+\\[A-Za-z0-9_.$-]+)\b")


def _uuid_fragment_matches(ref_uuid: str, actual_uuid: str | None) -> bool:
    if not actual_uuid:
        return False
    ref = ref_uuid.strip().lower()
    actual = actual_uuid.strip().lower()
    if ref == actual:
        return True
    if len(ref) >= 8 and (actual.endswith(ref) or ref in actual):
        return True
    return False


def excerpt_matches(ref: EvidenceRef, obs: Observation) -> bool:
    if not ref.excerpt:
        return True
    excerpt = ref.excerpt.strip().lower()
    value = obs.value.strip().lower()
    return excerpt == value or excerpt in value or value in excerpt


def resolve_observation(ref: EvidenceRef, manifest: EvidenceManifest) -> Observation | None:
    idx = manifest.observation_index()
    exact = idx.get(ref.obs_id)
    if exact is not None:
        return exact

    ref_evt, ref_kind, ref_slug = parse_obs_id(ref.obs_id)
    candidates: list[Observation] = []
    for candidate in manifest.observations:
        if ref_kind and candidate.kind != ref_kind:
            continue
        _, _, cand_slug = parse_obs_id(candidate.obs_id)
        slug_match = bool(
            ref_slug
            and (
                ref_slug == slug_observation_value(candidate.value)
                or ref_slug == cand_slug
                or ref_slug in candidate.obs_id
            )
        )
        if not slug_match:
            continue
        evt_uuid, _, _ = parse_obs_id(candidate.obs_id)
        uuid_match = (
            not ref_evt
            or _uuid_fragment_matches(ref_evt, candidate.event_uuid)
            or _uuid_fragment_matches(ref_evt, evt_uuid)
        )
        if uuid_match:
            candidates.append(candidate)

    if len(candidates) == 1:
        return candidates[0]

    if ref.excerpt:
        excerpt = ref.excerpt.strip().lower()
        for candidate in candidates or manifest.observations:
            val = candidate.value.strip().lower()
            if excerpt == val or excerpt in val or val in excerpt:
                return candidate
    return None


def observation_supports_ref(ref: EvidenceRef, manifest: EvidenceManifest) -> bool:
    obs = resolve_observation(ref, manifest)
    if obs is None:
        return False
    return excerpt_matches(ref, obs)


def extract_entities(summary: str) -> list[tuple[str, str]]:
    entities: list[tuple[str, str]] = []
    for match in _PROCESS_ENTITY.finditer(summary):
        entities.append(("process", match.group(1)))
    for match in _PID_ENTITY.finditer(summary):
        entities.append(("pid", match.group(1)))
    for match in _PIPE_ENTITY.finditer(summary):
        entities.append(("pipe", match.group(1)))
    for match in _ACCOUNT_ENTITY.finditer(summary):
        entities.append(("account", match.group(1)))
    return entities


def entity_grounded(entity_type: str, value: str, manifest: EvidenceManifest) -> bool:
    needle = value.lower()
    for obs in manifest.observations:
        if obs.kind == entity_type and needle in obs.value.lower():
            return True
    return False
