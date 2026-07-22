import { isPlainObject } from "@/lib/json-display"

export const PROFILE_MARKERS = new Set([
  "summary",
  "finding",
  "topic",
  "evidence",
  "risk_level",
  "severity",
  "priority",
  "analysis",
  "message",
  "data_gaps",
  "recommendations",
  "recommended_actions",
  "recommended_remediation",
  "mitre_tactics",
  "mitre_techniques",
  "telemetry_level",
  "confidence",
  "affected_assets",
  "affected_systems",
  "timeline",
  "references",
  "finding_type",
  "attack_phase",
  "ttl",
  "hypothesis",
  "hunt_status",
  "technique_ids",
  "detection_gaps",
  "actor_profile",
  "ttps",
  "iocs",
  "recon_indicators",
  "identity_asset",
  "attack_path",
  "credential_indicators",
  "lateral_movement_stage",
  "artifacts",
  "containment_status",
  "eradication_steps",
  "forensic_confidence",
  "cloud_provider",
  "resource_id",
  "misconfig_type",
  "blast_radius",
  "remediation",
  "framework",
  "control_id",
  "compliance_status",
  "gaps",
  "reproduction_steps",
  "incident_id",
  "related_findings",
  "kill_chain_phases_completed",
  "attack_coverage_map",
  "recommended_atomic_tests",
  "d3fend_controls",
])

/** @deprecated Use PROFILE_MARKERS — kept for existing imports */
export const FINDING_MARKERS = PROFILE_MARKERS

export function formatFindingField(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

const META_KEYS = new Set(["persona", "job_id", "agent", "event_id", "correlation_id", "tenant_id", "sandbox_id"])

export function findingBody(item: unknown): Record<string, unknown> {
  if (!isPlainObject(item)) return {}
  const nested = item.finding
  if (isPlainObject(nested)) return nested
  return item
}

export function findingEnvelope(item: Record<string, unknown>): {
  body: Record<string, unknown>
  evidenceManifest?: Record<string, unknown>
} {
  const body = findingBody(item)
  const manifest = item.evidence_manifest
  return {
    body,
    evidenceManifest: isPlainObject(manifest) ? manifest : undefined,
  }
}

export function hasFindingValue(value: unknown): boolean {
  if (value === undefined || value === null || value === "") return false
  if (Array.isArray(value)) return value.length > 0
  if (isPlainObject(value)) return Object.keys(value).length > 0
  return true
}

export function isDisplayableFindingKey(key: string): boolean {
  return !META_KEYS.has(key) && key !== "raw_response" && key !== "evidence_manifest"
}

export function mergeFindingContext(
  body: Record<string, unknown>,
  evidenceManifest?: Record<string, unknown>,
): Record<string, unknown> {
  if (!evidenceManifest) return body
  const merged = { ...body }
  if (!hasFindingValue(merged.telemetry_level) && evidenceManifest.telemetry_level) {
    merged.telemetry_level = evidenceManifest.telemetry_level
  }
  if (!hasFindingValue(merged.data_gaps) && evidenceManifest.data_gaps) {
    merged.data_gaps = evidenceManifest.data_gaps
  }
  if (!hasFindingValue(merged.mitre_techniques) && evidenceManifest.suggested_mitre_techniques) {
    merged.mitre_techniques = evidenceManifest.suggested_mitre_techniques
  }
  if (!hasFindingValue(merged.evidence) && evidenceManifest.observations) {
    merged.evidence = evidenceManifest.observations
  }
  return merged
}

/** Keep the latest finding per persona (bus retries append newer entries). */
export function dedupeFindingsByPersona(findings: Record<string, unknown>[]): Record<string, unknown>[] {
  const seen = new Set<string>()
  const result: Record<string, unknown>[] = []
  for (let index = findings.length - 1; index >= 0; index -= 1) {
    const item = findings[index]
    const persona = typeof item.persona === "string" ? item.persona.trim() : ""
    const key = persona || `__anonymous_${index}`
    if (seen.has(key)) continue
    seen.add(key)
    result.unshift(item)
  }
  return result
}
