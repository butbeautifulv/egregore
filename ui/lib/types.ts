export type {
  CatalogEvaluation,
  CatalogProfile,
  InvestigationDetail,
  InvestigationSummary,
  JobSummary,
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
