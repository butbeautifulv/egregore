const API_BASE = process.env.NEXT_PUBLIC_EGREGORE_API_URL ?? "http://localhost:8080"

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = "ApiError"
  }
}

function headers(): HeadersInit {
  const result: Record<string, string> = {
    "Content-Type": "application/json",
  }
  const token = process.env.NEXT_PUBLIC_EGREGORE_API_TOKEN
  if (token) {
    result.Authorization = `Bearer ${token}`
  }
  return result
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...headers(),
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new ApiError(detail || response.statusText, response.status)
  }
  return response.json() as Promise<T>
}

export type StatusSnapshot = {
  events_count: number
  findings_count: number
  latest_narrative: string
  events: unknown[]
  findings: unknown[]
  critic_feedback: unknown[]
  narratives: string[]
  awaiting_approval: unknown[]
  escalations: unknown[]
}

export function getStatus() {
  return request<StatusSnapshot>("/status")
}

export type PostEventResponse = {
  event: { id: string; correlation_id?: string; type: string }
  routing: { personas: string[]; reason?: string }
  job_ids: string[]
  accepted?: boolean
  planner_status?: string
}

export function postEvent(body: {
  event_type: string
  payload: Record<string, unknown>
  severity?: string
  source?: string
  correlation_id?: string
}) {
  return request<PostEventResponse>("/events", {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export type InvestigationSummary = {
  investigation_id: string
  tenant_id: string
  goal: string
  status: string
  completed_personas: string[]
  updated_at?: string
}

export type InvestigationDetail = InvestigationSummary & {
  planner_plan: string[] | null
  planner_status?: string | null
  planner_rationale?: string
  planner_error?: string
  findings_summary: Record<string, unknown>[]
}

export type JobSummary = {
  job_id: string
  persona: string
  status: string
  session_id: string
  correlation_id: string
  event_id: string
}

export function listInvestigations(tenantId = "default", limit = 20) {
  return request<{ investigations: InvestigationSummary[] }>(
    `/investigations?tenant_id=${encodeURIComponent(tenantId)}&limit=${limit}`,
  )
}

export function getInvestigation(investigationId: string, tenantId = "default") {
  return request<InvestigationDetail>(
    `/investigations/${encodeURIComponent(investigationId)}?tenant_id=${encodeURIComponent(tenantId)}`,
  )
}

export function getInvestigationJobs(investigationId: string, tenantId = "default") {
  return request<{ jobs: JobSummary[] }>(
    `/investigations/${encodeURIComponent(investigationId)}/jobs?tenant_id=${encodeURIComponent(tenantId)}`,
  )
}

export type PendingApproval = {
  job_id: string
  session_id: string
  persona: string
  tool_name: string
  tool_args: Record<string, unknown>
  risk_level: string
  approval_id: string
}

export function listPendingApprovals() {
  return request<{ count: number; approvals: PendingApproval[] }>("/approvals/pending")
}

export function resumeJob(
  jobId: string,
  body: { decision: string; approval_id?: string; actor?: string; edited_args?: Record<string, unknown> },
) {
  return request<Record<string, unknown>>(`/jobs/${encodeURIComponent(jobId)}/resume`, {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export function statusStreamUrl() {
  return `${API_BASE}/status/stream`
}
