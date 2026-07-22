import type { EngagementStreamEvent } from "@/lib/api-client"
import { findingBody } from "@/lib/finding-display"
import { parseJsonMaybe, plannerPlanFromDetail } from "@/lib/json-display"
import { isPlaybookSearchTool, parsePlaybookSearchPreview } from "@/lib/tool-call-display"
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
    agentExpanded: false,
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
    const seq = payload.seq ?? ""
    return [type, payload.job_id ?? "", seq, payload.delta ?? ""].join("|")
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
  if (type === "hitl_pending" || type === "hitl_resolved") {
    return [type, payload.job_id ?? "", payload.approval_id ?? "", payload.decision ?? ""].join("|")
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
  const payload = eventPayload(event)
  if (payload.success === false && (type === "job_finished" || (type === "status" && phase === "job_finished"))) {
    return false
  }
  if (type === "hitl_resolved") {
    return true
  }
  if (["assistant_done", "job_finished", "job_started", "error", "control", "report", "outcome_ready"].includes(type)) {
    return true
  }
  if (type === "status" && phase === "final_report") {
    return true
  }
  if (
    type === "status" &&
    [
      "job_started",
      "job_finished",
      "job_enqueued",
      "error",
      "planning_done",
      "planning_error",
    ].includes(phase)
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

function shouldApplyControlEvent(type: string, payload: Record<string, unknown>): boolean {
  if (type === "report") {
    return false
  }
  if (type !== "control") {
    return true
  }
  const verdict = payload.verdict
  if (verdict && typeof verdict === "object" && !Array.isArray(verdict)) {
    const record = verdict as Record<string, unknown>
    if (
      record.passed === true &&
      !record.auto_accepted_after_revision_cap &&
      !record.revision_enqueued
    ) {
      return false
    }
  }
  return true
}

function controlEventText(type: string, payload: Record<string, unknown>): string {
  if (type === "control_error") return String(payload.error ?? "control error")
  if (type === "report") return String(payload.summary ?? "")
  const operatorMessage = payload.operator_message
  if (typeof operatorMessage === "string" && operatorMessage.trim()) {
    return operatorMessage.trim()
  }
  const verdict = payload.verdict
  if (verdict && typeof verdict === "object" && !Array.isArray(verdict)) {
    const record = verdict as Record<string, unknown>
    const issues = [
      ...(Array.isArray(record.issues_detected) ? record.issues_detected.map(String) : []),
      ...(Array.isArray(record.rejected_claims) ? record.rejected_claims.map(String) : []),
    ].filter(Boolean)
    const source = String(payload.source_persona ?? "agent")
    if (record.auto_accepted_after_revision_cap) {
      return `Quality check for ${source}: revision cap reached; result accepted automatically.`
    }
    if (issues.length) {
      return `Quality check failed (${source}): ${issues.join(", ")}. Revision requested.`
    }
  }
  if (verdict && typeof verdict === "object") return JSON.stringify(verdict, null, 2)
  return JSON.stringify(payload, null, 2)
}

export type JobFailureInput = {
  error?: string
  reason?: string
}

export function formatJobFailure({ error = "", reason = "" }: JobFailureInput): string {
  const err = error.trim()
  const reasonKey = reason.trim().toLowerCase()

  if (reasonKey === "schema_invalid") {
    if (err.startsWith("empty_finding:")) {
      const gaps = err.slice("empty_finding:".length).replace(/,/g, ", ")
      return `Agent finished without a valid structured result (missing: ${gaps}).`
    }
    return "Agent finished without a valid structured result."
  }
  if (reasonKey === "grounding_rejected") {
    if (err.startsWith("ungrounded_finding:")) {
      const detail = err.slice("ungrounded_finding:".length).replace(/,/g, ", ")
      return `Result failed evidence or grounding checks: ${detail}`
    }
    return "Result failed evidence or grounding checks."
  }
  if (reasonKey === "llm_error") {
    if (err.startsWith("model_refusal:")) {
      return `Model refused: ${err.slice("model_refusal:".length)}`
    }
    return "Model refused or returned unusable output."
  }
  if (reasonKey === "tool_error") {
    if (err.startsWith("tools_not_executed:")) {
      return `Tools were planned but never executed. ${err.slice("tools_not_executed:".length)}`
    }
    return "A tool call failed during this run."
  }
  if (reasonKey === "tool_invalid_args") {
    return "A tool was called with invalid arguments."
  }
  if (reasonKey === "timeout") {
    return "The agent run timed out before completing."
  }
  if (reasonKey === "budget_exceeded") {
    return "The agent run exceeded its cost or token budget."
  }
  if (reasonKey === "sandbox_error") {
    return "The execution sandbox failed."
  }
  if (reasonKey === "security_violation") {
    return "The run was blocked by a security policy."
  }
  if (reasonKey === "cancelled") {
    return "The agent run was cancelled."
  }

  return formatJobError(err || reason || "Agent job failed")
}

/** @deprecated Prefer formatJobFailure({ error, reason }) */
export function formatJobError(err: string): string {
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
  if (err.startsWith("ungrounded_finding:")) {
    const detail = err.slice("ungrounded_finding:".length).replace(/,/g, ", ")
    return `Finding failed quality checks (evidence grounding): ${detail}`
  }
  if (err.startsWith("noop_finding")) {
    return "Agent completed without a new substantive finding."
  }
  if (err.includes("insufficient tool messages")) {
    return "Model tool-call history was corrupted (parallel tools). Retry the work order or run agents sequentially."
  }
  const messageMatch = err.match(/"message":"([^"]+)"/)
  if (messageMatch?.[1]) {
    return `Job failed: ${messageMatch[1]}`
  }
  if (err.length > 280) {
    return `Job failed: ${err.slice(0, 280)}…`
  }
  return `Job failed: ${err}`
}

function findToolByCallId(entry: AgentChatEntry, toolCallId: string): ChatToolCall | undefined {
  if (!toolCallId) return undefined
  return entry.tools.find((tool) => tool.tool_call_id === toolCallId)
}

function findStartedTool(
  entry: AgentChatEntry,
  toolCallId: string,
  toolName: string,
): ChatToolCall | undefined {
  if (toolCallId) {
    const byId = findToolByCallId(entry, toolCallId)
    if (byId) return byId
  }
  return entry.tools.find(
    (tool) => tool.status === "started" && tool.name.startsWith(toolName),
  )
}

function upsertToolStart(entry: AgentChatEntry, tool: ChatToolCall): void {
  if (tool.tool_call_id) {
    const existing = findToolByCallId(entry, tool.tool_call_id)
    if (existing) {
      existing.name = tool.name
      existing.status = "started"
      if (tool.tool_args) existing.tool_args = tool.tool_args
      return
    }
  }
  entry.tools.push(tool)
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

  if (type === "hitl_pending") {
    entry.hitl = {
      approvalId: String(payload.approval_id ?? ""),
      toolName: String(payload.tool_name ?? payload.tool ?? "tool"),
      toolArgs:
        payload.tool_args && typeof payload.tool_args === "object"
          ? (payload.tool_args as Record<string, unknown>)
          : payload.args && typeof payload.args === "object"
            ? (payload.args as Record<string, unknown>)
            : {},
      riskLevel: String(payload.risk_level ?? payload.risk ?? ""),
      status: "pending",
    }
    entry.streaming = false
    return true
  }

  if (type === "hitl_resolved") {
    const decision = String(payload.decision ?? "")
    if (entry.hitl) {
      entry.hitl.status = decision === "reject" ? "rejected" : "approved"
    }
    if (decision === "reject") {
      entry.jobError = "hitl_rejected"
      entry.buffer = formatJobFailure({ error: "hitl_rejected", reason: "cancelled" })
      entry.streaming = false
    }
    return true
  }

  if (controlTypes.includes(type)) {
    if (!shouldApplyControlEvent(type, payload)) {
      return false
    }
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
    const delta = String(payload.delta ?? "")
    if (!delta) return false
    const seqRaw = payload.seq
    const seq = seqRaw != null && seqRaw !== "" ? Number(seqRaw) : null
    if (seq != null && !Number.isNaN(seq)) {
      const last = entry.lastAssistantSeq ?? 0
      if (seq <= last) return false
      entry.lastAssistantSeq = seq
    } else if (entry.buffer.endsWith(delta)) {
      return false
    }
    entry.buffer += delta
    entry.streaming = true
    return true
  }

  if (type === "assistant_snapshot") {
    const text = String(payload.text ?? "")
    if (!text) {
      entry.streaming = false
      return false
    }
    if (entry.buffer === text) {
      entry.streaming = false
      return false
    }
    if (entry.buffer && text.includes(entry.buffer)) {
      entry.buffer = text
      entry.streaming = false
      return true
    }
    if (entry.buffer && entry.buffer.includes(text)) {
      entry.streaming = false
      return false
    }
    if (!entry.buffer) {
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

  if (type === "status" && event.phase === "job_started") {
    entry.streaming = true
    entry.agentExpanded = true
    return true
  }

  if (type === "outcome_ready") {
    const outcome = payload.outcome
    if (outcome && typeof outcome === "object" && !Array.isArray(outcome)) {
      const record = outcome as Record<string, unknown>
      const summary = record.summary ? String(record.summary).trim() : ""
      entry.buffer = summary || JSON.stringify(record, null, 2)
    }
    entry.streaming = false
    return true
  }

  if (type === "status" && event.phase === "final_report") {
    const report = payload.report
    if (report && typeof report === "object" && !Array.isArray(report)) {
      const record = report as Record<string, unknown>
      const summary = record.summary ? String(record.summary).trim() : ""
      entry.buffer = summary || JSON.stringify(record, null, 2)
    }
    entry.streaming = false
    return true
  }

  if (type === "status" && event.phase === "job_finished") {
    const err = String(payload.error ?? "unknown")
    const reason = payload.reason ? String(payload.reason) : ""
    if (payload.success === false) {
      entry.jobError = err
      entry.buffer = formatJobFailure({ error: err, reason })
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
    const toolArgs =
      payload.tool_args && typeof payload.tool_args === "object"
        ? (payload.tool_args as ChatToolCall["tool_args"])
        : undefined
    upsertToolStart(entry, {
      name: label,
      status: "started",
      tool_call_id: toolCallId || undefined,
      tool_args: toolArgs,
    })
    return true
  }

  if (type === "skill_loaded") {
    const skill = String(payload.skill_name ?? payload.skill ?? "skill")
    const label = `load_skill → ${skill}`
    const duplicate = entry.tools.some((tool) => tool.name === label && tool.status === "done")
    if (!duplicate) {
      entry.tools.push({ name: label, status: "done" })
    }
    return true
  }

  if (type === "tool_done" && features.streamAgentTools) {
    const toolCallId = String(payload.tool_call_id ?? "")
    const toolName = String(payload.tool_name ?? "tool")
    const outputPreview = payload.output_preview ? String(payload.output_preview) : ""
    const match = findStartedTool(entry, toolCallId, toolName)
    if (match) {
      match.status = payload.ok === false ? "error" : "done"
      if (outputPreview) {
        match.output_preview = outputPreview
      }
      if (isPlaybookSearchTool(toolName) && outputPreview) {
        const parsed = parsePlaybookSearchPreview(outputPreview)
        if (parsed) {
          match.playbook_result = parsed
        }
      }
    } else if (toolCallId && findToolByCallId(entry, toolCallId)) {
      // Replay after tool_done already applied — no-op.
    } else {
      const tool: ChatToolCall = {
        name: toolName,
        status: payload.ok === false ? "error" : "done",
        tool_call_id: toolCallId || undefined,
      }
      if (outputPreview) {
        tool.output_preview = outputPreview
        if (isPlaybookSearchTool(toolName)) {
          const parsed = parsePlaybookSearchPreview(outputPreview)
          if (parsed) tool.playbook_result = parsed
        }
      }
      entry.tools.push(tool)
    }
    return true
  }

  if (type === "tool_error" && features.streamAgentTools) {
    const toolCallId = String(payload.tool_call_id ?? "")
    const toolName = String(payload.tool_name ?? "tool")
    const errorMessage = String(payload.error ?? "tool error")
    const match = findStartedTool(entry, toolCallId, toolName)
    if (match) {
      match.status = "error"
      match.error_message = errorMessage
    } else if (toolCallId && findToolByCallId(entry, toolCallId)) {
      // Replay after tool_error already applied — no-op.
    } else {
      entry.tools.push({
        name: toolName,
        status: "error",
        tool_call_id: toolCallId || undefined,
        error_message: errorMessage,
      })
    }
    return true
  }

  return false
}

export function hydrateHitlFromPending(
  state: ChatStateMap,
  approvals: {
    job_id: string
    approval_id: string
    tool_name: string
    tool_args?: Record<string, unknown>
    risk_level?: string
    persona?: string
  }[],
  jobIds: Set<string>,
): void {
  for (const approval of approvals) {
    if (!jobIds.has(approval.job_id)) continue
    const entry = ensureChatEntry(state, approval.job_id, approval.persona)
    if (entry.hitl?.status === "approved" || entry.hitl?.status === "rejected") continue
    entry.hitl = {
      approvalId: approval.approval_id,
      toolName: approval.tool_name,
      toolArgs: approval.tool_args ?? {},
      riskLevel: approval.risk_level ?? "",
      status: "pending",
    }
    entry.streaming = false
  }
}

export function hydrateFailedJobsFromList(
  state: ChatStateMap,
  jobs: { job_id: string; persona: string; status: string; error?: string; reason?: string }[],
  failedPersonas: string[] = [],
): void {
  for (const job of jobs) {
    if (job.status !== "failed") continue
    const entry = ensureChatEntry(state, job.job_id, job.persona)
    if (entry.jobError || entry.buffer) continue
    const err = job.error?.trim() || ""
    const reason = job.reason?.trim() || ""
    entry.jobError = err || reason || "Agent job failed"
    entry.buffer = formatJobFailure({ error: err, reason })
    entry.streaming = false
  }
  for (const persona of failedPersonas) {
    const job = jobs.find((item) => item.persona === persona && item.status === "failed")
    if (job) continue
    const placeholderId = `${persona}:failed`
    const entry = ensureChatEntry(state, placeholderId, persona)
    if (entry.jobError || entry.buffer) continue
    entry.jobError = "Agent job failed"
    entry.buffer = formatJobError("Agent job failed")
    entry.streaming = false
  }
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
    if (!entry.buffer && !entry.jobError) {
      entry.buffer = formatFindingText(item.finding ?? item)
    }
  }
  const plannerId = plannerJobId(engagementId)
  const plannerEntry = ensureChatEntry(state, plannerId, "planner")
  if (
    !plannerEntry.buffer &&
    !plannerEntry.streaming &&
    (plannerPlan?.length || plannerRationale)
  ) {
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
