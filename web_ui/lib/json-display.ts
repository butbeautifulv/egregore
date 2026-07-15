export function isPlainObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}

export function parseJsonMaybe(text: string): unknown | null {
  const trimmed = text.trim()
  if (!trimmed) return null
  if (!(trimmed.startsWith("{") || trimmed.startsWith("["))) return null
  try {
    return JSON.parse(trimmed) as unknown
  } catch {
    return null
  }
}

export function isPlannerPlanPayload(value: unknown): value is Record<string, unknown> {
  if (!isPlainObject(value)) return false
  return Array.isArray(value.personas) || isPlainObject(value.sub_goals)
}

import { FINDING_MARKERS } from "@/lib/finding-display"

export function isFindingPayload(value: unknown): value is Record<string, unknown> {
  if (!isPlainObject(value)) return false
  if (isPlannerPlanPayload(value)) return false
  return Object.keys(value).some((key) => FINDING_MARKERS.has(key))
}

export function plannerPlanFromDetail(detail: {
  planner_plan?: string[] | null
  planner_rationale?: string
  planner_sub_goals?: Record<string, string>
  planner_depends_on?: Record<string, string[]>
  execution_mode?: string | null
  synthesis_persona?: string | null
}): Record<string, unknown> {
  return {
    personas: detail.planner_plan ?? [],
    sub_goals: detail.planner_sub_goals ?? {},
    depends_on: detail.planner_depends_on ?? {},
    rationale: detail.planner_rationale ?? "",
    execution_mode: detail.execution_mode ?? null,
    synthesis_persona: detail.synthesis_persona ?? null,
  }
}

export function formatJsonLabel(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

export function jsonPreview(value: unknown, maxLength = 120): string {
  if (value === null || value === undefined) return "—"
  if (typeof value === "string") {
    return value.length <= maxLength ? value : `${value.slice(0, maxLength)}…`
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value)
  }
  const serialized = JSON.stringify(value)
  return serialized.length <= maxLength ? serialized : `${serialized.slice(0, maxLength)}…`
}
