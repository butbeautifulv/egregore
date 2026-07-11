import type { EngagementStreamEvent } from "@/lib/api-client"
import { findingBody } from "@/lib/finding-display"
import { parseJsonMaybe, plannerPlanFromDetail } from "@/lib/json-display"
import type { AgentChatEntry, ApiFeatures, ChatReasoning, ChatToolCall } from "@/lib/types"

export const CHAT_THROTTLE_MS = 50

export type ChatStateMap = Map<string, AgentChatEntry>

export function plannerJobId(engagementId: string): string {
  return `planner:${engagementId}`
}

export function createChatEntry(jobId: string, persona = "agent"): AgentChatEntry {
  return {
    jobId,
    persona,
    buffer: "",
    turns: [],
    reasoning: null,
    tools: [],
    streaming: false,
    agentExpanded: true,
    jobError: "",
    isControlError: false,
  }
}

export function ensureChatEntry(state: ChatStateMap, jobId: string, persona?: string): AgentChatEntry {
  const existing = state.get(jobId)
  if (existing) {
    if (persona && (existing.persona === "agent" || !existing.persona)) {
      existing.persona = persona
    }
    return existing
  }
  const entry = createChatEntry(jobId, persona ?? "agent")
  state.set(jobId, entry)
  return entry
}

export function eventPayload(event: EngagementStreamEvent): Record<string, unknown> {
  return event.payload ?? {}
}

export function eventDedupeKey(event: EngagementStreamEvent): string {
  const payload = eventPayload(event)
  const type = event.type ?? ""
  if (type === "assistant_delta") {
    return [type, payload.job_id ?? "", payload.seq ?? "", payload.delta ?? ""].join("|")
  }
  if (type === "reasoning_delta") {
    return [
      type,
      payload.job_id ?? "",
      payload.plan_status ?? "",
      (Array.isArray(payload.reasoning_steps) ? payload.reasoning_steps : []).join(","),
    ].join("|")
  }
  if (type === "assistant_snapshot") {
    return [type, payload.job_id ?? "", payload.text ?? ""].join("|")
  }
  if (type === "tool_start" || type === "tool_done" || type === "tool_error") {
    const preview = payload.output_preview ? String(payload.output_preview).slice(0, 64) : ""
    return [
      type,
      payload.job_id ?? "",
      payload.tool_name ?? "",
      payload.tool_call_id ?? "",
      preview,
      payload.error ?? "",
    ].join("|")
  }
  return [
    type,
    event.phase ?? "",
    payload.job_id ?? "",
    payload.persona ?? "",
    payload.summary ?? "",
    JSON.stringify(payload.verdict ?? ""),
  ].join("|")
}

export function shouldRefreshOnEvent(event: EngagementStreamEvent): boolean {
  const type = event.type ?? ""
  const phase = event.phase ?? ""
  if (["assistant_done", "job_finished", "job_started", "error", "control", "report"].includes(type)) {
    return true
  }
  if (type === "status" && phase === "final_report") {
    return true
  }
  if (
    type === "status" &&
    ["job_started", "job_finished", "error", "planning_done", "planning_error"].includes(phase)
  ) {
    return true
  }
  return false
}

function resolveControlJobId(type: string, payload: Record<string, unknown>, engagementId: string): string {
  if (payload.job_id) return String(payload.job_id)
  if (type === "report") return `coordinator:${engagementId}`
  return `critic:${engagementId}`
}

function controlEventText(type: string, payload: Record<string, unknown>): string {
  if (type === "control_error") return String(payload.error ?? "control error")
  if (type === "report") return String(payload.summary ?? "")
  const verdict = payload.verdict
  if (verdict && typeof verdict === "object") return JSON.stringify(verdict, null, 2)
  return JSON.stringify(payload, null, 2)
}

function formatJobError(err: string): string {
  if (err.startsWith("tools_not_executed:")) {
    return `Tools were planned in JSON but never executed. ${err.slice("tools_not_executed:".length)}`
  }
  if (err.startsWith("empty_finding:")) {
    const gaps = err.slice("empty_finding:".length).replace(/,/g, ", ")
    return `Agent finished without a valid finding (missing: ${gaps}).`
  }
  if (err === "empty_finding") {
    return "Agent finished without a valid finding (model may have refused or returned invalid JSON)."
  }
  if (err.startsWith("model_refusal:")) {
    return `Model refused: ${err.slice("model_refusal:".length)}`
  }
  return `Job failed: ${err}`
}

export function applyChatEvent(
  state: ChatStateMap,
  event: EngagementStreamEvent,
  features: ApiFeatures,
  engagementId: string,
): boolean {
  const type = event.type ?? ""
  const payload = eventPayload(event)
  const controlTypes = ["control", "report", "control_error"]
  let jobId = payload.job_id ? String(payload.job_id) : ""
  let persona = payload.persona ? String(payload.persona) : undefined
  if (!jobId && controlTypes.includes(type)) {
    jobId = resolveControlJobId(type, payload, engagementId)
    persona = persona ?? (type === "report" ? "coordinator" : "critic")
  }
  if (!jobId) return false

  const entry = ensureChatEntry(state, jobId, persona)

  if (controlTypes.includes(type)) {
    entry.buffer = controlEventText(type, payload)
    entry.streaming = false
    entry.isControlError = type === "control_error"
    return true
  }

  if (type === "reasoning_delta") {
    entry.reasoning = {
      current_situation: String(payload.current_situation ?? ""),
      plan_status: String(payload.plan_status ?? ""),
      reasoning_steps: Array.isArray(payload.reasoning_steps)
        ? payload.reasoning_steps.map(String)
        : [],
      task_completed: Boolean(payload.task_completed),
    }
    return true
  }

  if (type === "assistant_delta") {
    entry.buffer += String(payload.delta ?? "")
    entry.streaming = true
    return true
  }

  if (type === "assistant_snapshot") {
    const text = String(payload.text ?? "")
    if (text && entry.buffer === text) {
      entry.streaming = false
      return false
    }
    if (!entry.buffer && text) {
      entry.buffer = text
    }
    entry.streaming = false
    return true
  }

  if (type === "assistant_done") {
    if (entry.buffer) {
      const lastTurn = entry.turns.at(-1)
      if (lastTurn !== entry.buffer) {
        entry.turns.push(entry.buffer)
      }
      entry.buffer = ""
    }
    entry.streaming = false
    return true
  }

  if (type === "status" && event.phase === "job_finished") {
    const err = String(payload.error ?? "unknown")
    if (payload.success === false) {
      entry.jobError = err
      if (!entry.buffer) {
        entry.buffer = formatJobError(err)
      }
      entry.agentExpanded = false
    } else {
      entry.jobError = ""
    }
    entry.streaming = false
    return true
  }

  if (type === "tool_start" && features.streamAgentTools) {
    const toolName = String(payload.tool_name ?? "tool")
    const toolCallId = String(payload.tool_call_id ?? "")
    const label = payload.skill_name ? `${toolName} → ${payload.skill_name}` : toolName
    entry.tools.push({ name: label, status: "started", tool_call_id: toolCallId })
    return true
  }

  if (type === "skill_loaded") {
    const skill = String(payload.skill_name ?? payload.skill ?? "skill")
    entry.tools.push({ name: `load_skill → ${skill}`, status: "done" })
    return true
  }

  if (type === "tool_done" && features.streamAgentTools) {
    const toolCallId = String(payload.tool_call_id ?? "")
    const toolName = String(payload.tool_name ?? "tool")
    const match = entry.tools.find(
      (tool) =>
        tool.status === "started" &&
        (tool.tool_call_id === toolCallId || tool.name.startsWith(toolName)),
    )
    if (match) {
      match.status = payload.ok === false ? "error" : "done"
    } else {
      entry.tools.push({ name: toolName, status: payload.ok === false ? "error" : "done" })
    }
    return true
  }

  if (type === "tool_error" && features.streamAgentTools) {
    const toolName = String(payload.tool_name ?? "tool")
    entry.tools.push({ name: toolName, status: "error" })
    return true
  }

  return false
}

export function hydrateChatFromDetail(
  state: ChatStateMap,
  engagementId: string,
  findings: Record<string, unknown>[],
  plannerPlan: string[] | null,
  plannerRationale: string,
  plannerDetail?: {
    planner_sub_goals?: Record<string, string>
    planner_depends_on?: Record<string, string[]>
    execution_mode?: string | null
    synthesis_persona?: string | null
  },
): void {
  for (const item of findings) {
    const jobId = item.job_id ? String(item.job_id) : ""
    if (!jobId) continue
    const entry = ensureChatEntry(state, jobId, item.persona ? String(item.persona) : undefined)
    if (!entry.buffer) {
      entry.buffer = formatFindingText(item.finding ?? item)
    }
  }
  const plannerId = plannerJobId(engagementId)
  const plannerEntry = ensureChatEntry(state, plannerId, "planner")
  if (!plannerEntry.buffer && (plannerPlan?.length || plannerRationale)) {
    plannerEntry.buffer = JSON.stringify(
      plannerPlanFromDetail({
        planner_plan: plannerPlan,
        planner_rationale: plannerRationale,
        planner_sub_goals: plannerDetail?.planner_sub_goals,
        planner_depends_on: plannerDetail?.planner_depends_on,
        execution_mode: plannerDetail?.execution_mode,
        synthesis_persona: plannerDetail?.synthesis_persona,
      }),
      null,
      2,
    )
  }
}

export function formatFindingText(finding: unknown): string {
  const data = findingBody(finding)
  if (!Object.keys(data).length) return "—"
  if (data.raw_response) {
    const raw = String(data.raw_response)
    const parsed = parseJsonMaybe(raw)
    if (parsed) {
      return JSON.stringify(parsed, null, 2)
    }
    return raw
  }
  return JSON.stringify(data, null, 2)
}

export function sortChatEntries(
  entries: AgentChatEntry[],
  plannerId: string,
  plannerPlan: string[] | null,
  jobs: { job_id: string; persona: string }[],
): AgentChatEntry[] {
  const order: string[] = []
  order.push(plannerId)
  if (plannerPlan?.length) {
    for (const persona of plannerPlan) {
      const job = jobs.find((item) => item.persona === persona)
      if (job) order.push(job.job_id)
    }
  }
  for (const job of jobs) {
    if (!order.includes(job.job_id)) order.push(job.job_id)
  }
  const rank = new Map(order.map((id, index) => [id, index]))
  return [...entries].sort((a, b) => (rank.get(a.jobId) ?? 999) - (rank.get(b.jobId) ?? 999))
}

export type { ChatReasoning, ChatToolCall }
