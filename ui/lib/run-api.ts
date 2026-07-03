export const MODES = ["plan", "ask", "agent", "debug"] as const
export type InteractionMode = (typeof MODES)[number]

export type RunContext = {
  context_id: string
  kind: string
  tenant_id: string
  // mode comes from API payload; keep it flexible for forward-compat
  mode?: string
  correlation_key: string
}

export type RunResponse = {
  run_context: RunContext
  result: Record<string, unknown>
  status?: string
}

export type WorkPlan = {
  rationale?: string
  proposed_workers?: string[]
  todos?: Array<{ id: string; content: string; status: string }>
  questions?: Array<{ id: string; question: string }>
  awaiting_user_input?: boolean
}

export {
  approvePlan,
  createRun,
  createSession,
  getRun,
  runStep,
} from "@/lib/api-client"
