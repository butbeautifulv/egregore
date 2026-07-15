import type { StatusStreamEvent } from "@/lib/types"

export function matchesInvestigation(event: StatusStreamEvent, investigationId: string): boolean {
  if (event.id === investigationId) {
    return true
  }
  const payload = event.payload
  const candidates = [
    payload.correlation_id,
    payload.investigation_id,
    (payload.event as Record<string, unknown> | undefined)?.correlation_id,
  ]
  return candidates.some((value) => typeof value === "string" && value === investigationId)
}

export function eventSummary(payload: Record<string, unknown>): string {
  for (const key of ["message", "status", "event_type", "type", "goal", "persona", "tool_name"]) {
    const value = payload[key]
    if (typeof value === "string" && value) {
      return value
    }
  }
  const preview = JSON.stringify(payload)
  return preview.length > 120 ? `${preview.slice(0, 117)}…` : preview
}
