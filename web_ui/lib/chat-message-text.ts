import { formatFindingText } from "@/lib/engagement-chat-state"
import { findingBody } from "@/lib/finding-display"
import type { AgentChatEntry } from "@/lib/types"

function proseFromFinding(finding?: Record<string, unknown>): string {
  if (!finding) return ""
  const data = findingBody(finding.finding ?? finding)
  const summary = String(data.summary ?? data.topic ?? data.finding ?? "").trim()
  if (summary) return summary
  return formatFindingText(finding.finding ?? finding)
}

export function resolveEntryCopyText(
  entry: AgentChatEntry,
  finding?: Record<string, unknown>,
): string {
  const parts = [...entry.turns]
  if (entry.buffer?.trim()) parts.push(entry.buffer.trim())
  if (parts.length) return parts.join("\n\n")
  return proseFromFinding(finding)
}
