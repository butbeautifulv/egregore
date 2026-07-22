export type {
  CatalogAgent,
  CatalogEvaluation,
  CatalogPlan,
  CatalogProfile,
  CatalogSkill,
  CatalogTool,
  EngagementStreamEvent,
  EngagementSummary,
  HealthResponse,
  InfraHealthResponse,
  InvestigationDetail,
  InvestigationSummary,
  JobSummary,
  MemoryEntry,
  PendingApproval,
  PostEventResponse,
  StatusSnapshot,
} from "@/lib/api-client"

export type PersonaStepState = "done" | "running" | "pending" | "failed"

export type StatusStreamEvent = {
  kind: string
  payload: Record<string, unknown>
  ts: string
  id?: string
}

export type ApiFeatures = {
  streamAgentOutput: boolean
  streamAgentTools: boolean
}

export type PlaybookHit = {
  id: string
  name: string
  description?: string
  attack_ids?: string[]
}

export type PlaybookSearchResult = {
  query: string
  count: number
  subdomain?: string
  skills: PlaybookHit[]
}

export type ChatToolCall = {
  name: string
  status: "started" | "done" | "error"
  tool_call_id?: string
  tool_args?: { query?: string; limit?: number; subdomain?: string }
  playbook_result?: PlaybookSearchResult
  output_preview?: string
  error_message?: string
}

export type ChatReasoning = {
  current_situation: string
  plan_status: string
  reasoning_steps: string[]
  task_completed?: boolean
}

export type { FollowUpMessage, FollowUpSendResult } from "@/lib/follow-up"

export type AgentChatEntry = {
  jobId: string
  persona: string
  buffer: string
  turns: string[]
  reasoning: ChatReasoning | null
  tools: ChatToolCall[]
  streaming: boolean
  agentExpanded: boolean
  jobError: string
  isControlError: boolean
  /** Highest assistant_delta seq applied for this job (SSE replay idempotency). */
  lastAssistantSeq?: number
  hitl?: {
    approvalId: string
    toolName: string
    toolArgs: Record<string, unknown>
    riskLevel: string
    status: "pending" | "approved" | "rejected"
  }
}
