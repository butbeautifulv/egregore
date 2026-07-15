export type FollowUpRole = "operator" | "assistant"

export type FollowUpMode = "auto" | "qa" | "orchestrate" | "plan"
export type OperatorIntentMode = FollowUpMode

export type FollowUpContentType = "finding" | "plan" | "markdown"

export type FollowUpMessage = {
  id: string
  followUpId: string
  role: FollowUpRole
  text: string
  createdAt: string
  status: "queued" | "pending" | "completed" | "failed"
  persona?: string | null
  jobId?: string | null
  workKind?: string | null
  mode?: FollowUpMode | null
  contentType?: FollowUpContentType | null
  finding?: Record<string, unknown> | null
  streaming?: boolean
  error?: string
}

export type FollowUpTurn = {
  id: string
  role: string
  text: string
  created_at: string
  follow_up_id: string
  job_id?: string | null
  persona?: string | null
  status?: string
  work_kind?: string | null
  mode?: FollowUpMode | null
  content_type?: FollowUpContentType | null
  finding?: Record<string, unknown> | null
}

export type FollowUpSendResult = {
  follow_up_id: string
  status: "queued" | "pending" | "persisted"
  work_kind: string
  job_id?: string | null
}

export type FollowUpListResult = {
  turns: FollowUpTurn[]
}

export type FollowUpPair = {
  followUpId: string
  operator: FollowUpMessage
  assistant?: FollowUpMessage
}

export function isFollowUpJobId(jobId: string): boolean {
  return /-fu-/.test(jobId)
}

export function mapFollowUpStatus(status?: string): FollowUpMessage["status"] {
  if (status === "completed") return "completed"
  if (status === "failed") return "failed"
  if (status === "pending") return "pending"
  return "queued"
}

export function mapFollowUpTurn(turn: FollowUpTurn): FollowUpMessage {
  const role = turn.role === "assistant" ? "assistant" : "operator"
  const finding = turn.finding ?? null
  const text =
    role === "assistant" && finding
      ? JSON.stringify(finding, null, 2)
      : turn.text
  return {
    id: turn.id,
    followUpId: turn.follow_up_id,
    role,
    text,
    createdAt: turn.created_at,
    status: mapFollowUpStatus(turn.status),
    persona: turn.persona ?? null,
    jobId: turn.job_id ?? null,
    workKind: turn.work_kind ?? null,
    mode: turn.mode ?? null,
    contentType: turn.content_type ?? null,
    finding,
  }
}

export function isInitialTurn(followUpId: string): boolean {
  return followUpId.startsWith("wo-")
}

export function isFollowUpTurn(followUpId: string): boolean {
  return followUpId.startsWith("fu-")
}

export function splitInitialAndFollowUpPairs(messages: FollowUpMessage[]): {
  initialPair: FollowUpPair | null
  followUpPairs: FollowUpPair[]
} {
  const pairs = groupFollowUpPairs(messages)
  const initialPair = pairs.find((pair) => isInitialTurn(pair.followUpId)) ?? null
  const followUpPairs = pairs.filter((pair) => isFollowUpTurn(pair.followUpId))
  return { initialPair, followUpPairs }
}

export function groupFollowUpPairs(messages: FollowUpMessage[]): FollowUpPair[] {
  const byId = new Map<string, FollowUpPair>()
  for (const message of messages) {
    const existing = byId.get(message.followUpId)
    if (!existing) {
      if (message.role === "operator") {
        byId.set(message.followUpId, { followUpId: message.followUpId, operator: message })
      } else {
        byId.set(message.followUpId, {
          followUpId: message.followUpId,
          operator: {
            id: `placeholder-${message.followUpId}`,
            followUpId: message.followUpId,
            role: "operator",
            text: "",
            createdAt: message.createdAt,
            status: "queued",
          },
          assistant: message,
        })
      }
      continue
    }
    if (message.role === "operator") {
      existing.operator = message
    } else {
      existing.assistant = message
    }
  }
  return [...byId.values()].sort(
    (a, b) => new Date(a.operator.createdAt).getTime() - new Date(b.operator.createdAt).getTime(),
  )
}

import { isFindingPayload, isPlainObject, parseJsonMaybe } from "@/lib/json-display"
import type { AgentChatEntry } from "@/lib/types"
import type { JobSummary } from "@/lib/api-client"

/** Keep streamed finding JSON when follow_up_complete only carries a short summary. */
export function mergeFollowUpAnswerText(existing: string | undefined, incoming: string): string {
  const prev = (existing ?? "").trim()
  const next = incoming.trim()
  if (!prev) return next
  if (!next) return prev

  const prevParsed = parseJsonMaybe(prev)
  const nextParsed = parseJsonMaybe(next)
  if (prevParsed && isFindingPayload(prevParsed)) {
    if (!nextParsed || !isFindingPayload(nextParsed)) {
      return prev
    }
  }
  return next.length >= prev.length ? next : prev
}

export function parseFollowUpFinding(
  payload: Record<string, unknown>,
): Record<string, unknown> | null {
  const raw = payload.finding
  if (isPlainObject(raw)) return raw
  const text = String(payload.text ?? "").trim()
  const parsed = parseJsonMaybe(text)
  if (parsed && isPlainObject(parsed) && isFindingPayload(parsed)) {
    return parsed
  }
  return null
}

export function followUpContentTypeFromPayload(
  payload: Record<string, unknown>,
): FollowUpContentType | null {
  const explicit = payload.content_type
  if (explicit === "finding" || explicit === "plan" || explicit === "markdown") {
    return explicit
  }
  if (parseFollowUpFinding(payload)) return "finding"
  const text = String(payload.text ?? "").trim()
  const parsed = parseJsonMaybe(text)
  if (parsed && isPlainObject(parsed)) {
    if (Array.isArray((parsed as Record<string, unknown>).personas)) return "plan"
    if (isFindingPayload(parsed)) return "finding"
  }
  return text ? "markdown" : null
}

export function isFollowUpOrchestratorJob(jobId: string): boolean {
  return isFollowUpJobId(jobId)
}

export function buildFollowUpJobMap(
  jobs: JobSummary[],
  messages: FollowUpMessage[],
): Map<string, string> {
  const map = new Map<string, string>()
  for (const job of jobs) {
    const followUpId = job.follow_up_id?.trim()
    if (followUpId) map.set(job.job_id, followUpId)
  }
  for (const message of messages) {
    if (message.jobId && message.followUpId) {
      map.set(message.jobId, message.followUpId)
    }
  }
  return map
}

export function isFollowUpChildJob(jobId: string, followUpJobMap: Map<string, string>): boolean {
  return followUpJobMap.has(jobId) && !isFollowUpOrchestratorJob(jobId)
}

export function groupFollowUpChildEntries(
  entries: AgentChatEntry[],
  followUpJobMap: Map<string, string>,
): Map<string, AgentChatEntry[]> {
  const groups = new Map<string, AgentChatEntry[]>()
  for (const entry of entries) {
    const followUpId = followUpJobMap.get(entry.jobId)
    if (!followUpId || isFollowUpOrchestratorJob(entry.jobId)) continue
    const list = groups.get(followUpId) ?? []
    list.push(entry)
    groups.set(followUpId, list)
  }
  return groups
}

export function formatFollowUpMarkerLabel(
  workKind?: string | null,
  persona?: string | null,
  followUpId?: string | null,
): string {
  const initial = followUpId ? isInitialTurn(followUpId) : false
  if (workKind === "initial_qa" || (initial && (workKind === "follow_up_qa" || persona === "consultant"))) {
    return "Initial · Ask"
  }
  if (initial && workKind === "follow_up_plan") return "Initial · plan"
  if (workKind === "follow_up_plan") return "Follow-up · plan"
  if (workKind === "follow_up_orchestrate") return "Follow-up · Reinvestigate"
  if (workKind === "follow_up_qa" || persona === "consultant") return "Follow-up · Ask"
  if (initial) return "Initial message"
  return "Follow-up"
}

export function formatFollowUpRoleLabel(
  persona?: string | null,
  workKind?: string | null,
  followUpId?: string | null,
): string {
  const initial = followUpId ? isInitialTurn(followUpId) : false
  const p = persona ?? "assistant"
  if (workKind === "initial_qa" || (initial && workKind === "follow_up_qa")) {
    return `${p} · initial Ask · advisory only`
  }
  if (workKind === "follow_up_plan") {
    return `${p} · follow-up plan · may run agents`
  }
  if (initial && workKind === "follow_up_plan") {
    return `${p} · initial plan · may run agents`
  }
  if (workKind === "follow_up_orchestrate") {
    return `${p} · follow-up · may spawn workers`
  }
  if (workKind === "follow_up_qa" || p === "consultant") {
    return `${p} · follow-up Ask · read-only`
  }
  return `${p} · follow-up`
}
