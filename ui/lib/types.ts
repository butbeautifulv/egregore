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

export type ChatToolCall = {
  name: string
  status: "started" | "done" | "error"
  tool_call_id?: string
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
}
