const PROXY_BASE = "/api/egregore"
const UPSTREAM_BASE =
  process.env.EGREGORE_API_UPSTREAM ??
  (process.env.NODE_ENV === "development" ? "http://127.0.0.1:8080" : "http://egregore-api:8080")

function resolveApiBase(): string {
  if (typeof window !== "undefined") {
    return PROXY_BASE
  }
  // Server-side fetches (if any) talk to API directly inside the cluster.
  return UPSTREAM_BASE.replace(/\/$/, "")
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = "ApiError"
  }
}

export function apiAuthHeaders(): Record<string, string> {
  const result: Record<string, string> = {}
  const token = process.env.NEXT_PUBLIC_EGREGORE_API_TOKEN
  if (token) {
    result.Authorization = `Bearer ${token}`
  }
  return result
}

function headers(): HeadersInit {
  return {
    "Content-Type": "application/json",
    ...apiAuthHeaders(),
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${resolveApiBase()}${path}`, {
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
  investigation_id?: string
}

export type EngagementSummary = {
  engagement_id: string
  status: string
  job_ids: string[]
  playbook_id?: string
  reason?: string
  goal?: string
  completed_personas?: string[]
}

export function createEngagement(body: {
  goal: string
  profile_id?: string
  domain_id?: string
  mode?: string
  plan_strategy?: string
  tenant_id?: string
  correlation_id?: string
  input?: Record<string, unknown>
}) {
  return request<EngagementSummary>("/v1/engagements", {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export function getEngagement(engagementId: string, tenantId = "default") {
  return request<EngagementSummary>(
    `/v1/engagements/${encodeURIComponent(engagementId)}?tenant_id=${encodeURIComponent(tenantId)}`,
  )
}

export function engagementStreamUrl(engagementId: string, tenantId = "default") {
  const params = new URLSearchParams({ tenant_id: tenantId })
  return `${PROXY_BASE}/v1/engagements/${encodeURIComponent(engagementId)}/stream?${params}`
}

export function subscribeEngagementStream(
  engagementId: string,
  onEvent: (event: Record<string, unknown>) => void,
  tenantId = "default",
): () => void {
  const source = new EventSource(engagementStreamUrl(engagementId, tenantId))
  source.onmessage = (message) => {
    try {
      onEvent(JSON.parse(message.data) as Record<string, unknown>)
    } catch {
      // ignore malformed frames
    }
  }
  return () => source.close()
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
  return request<{ engagements: EngagementSummary[] }>(
    `/v1/engagements?tenant_id=${encodeURIComponent(tenantId)}&limit=${limit}`,
  ).then((data) => ({
    investigations: data.engagements.map((eng) => ({
      investigation_id: eng.engagement_id,
      tenant_id: tenantId,
      goal: eng.goal ?? "",
      status: eng.status,
      completed_personas: eng.completed_personas ?? [],
    })),
  }))
}

export function getInvestigation(investigationId: string, tenantId = "default") {
  return getEngagement(investigationId, tenantId).then((eng) => ({
    investigation_id: eng.engagement_id,
    tenant_id: tenantId,
    goal: "",
    status: eng.status,
    completed_personas: [],
    planner_plan: null,
    planner_status: null,
    planner_rationale: "",
    planner_error: "",
    findings_summary: [],
  }))
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
  return `${PROXY_BASE}/status/stream`
}

export type CatalogEvaluation = {
  persona: string
  empirical_trust: number
  sample_size: number
  declared_trust_level: string
}

export type CatalogProfile = {
  id: string
  name?: string
  description?: string
}

export function listCatalogEvaluations(profileId?: string) {
  const query = profileId ? `?profile_id=${encodeURIComponent(profileId)}` : ""
  return request<{ evaluations: CatalogEvaluation[] }>(`/catalog/evaluations${query}`)
}

export function listCatalogProfiles() {
  return request<{ profiles: CatalogProfile[] }>("/catalog/profiles")
}

export function getProfilePolicy(profileId: string) {
  return request<{
    profile_id: string
    profile: CatalogProfile | null
    policy: Record<string, unknown>
  }>(`/catalog/profiles/${encodeURIComponent(profileId)}/policy`)
}

export function putProfilePolicy(profileId: string, policy: Record<string, unknown>) {
  return request<{ profile_id: string; policy: Record<string, unknown> }>(
    `/catalog/profiles/${encodeURIComponent(profileId)}/policy`,
    {
      method: "PUT",
      body: JSON.stringify({ policy }),
    },
  )
}

export type RunResponse = {
  run_context: {
    context_id: string
    kind: string
    tenant_id: string
    mode?: string
    correlation_key: string
  }
  result: Record<string, unknown>
  status?: string
}

export function createSession(body: {
  goal: string
  message?: string
  mode?: string
}) {
  return request<RunResponse>("/sessions", {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export function createRun(body: {
  goal: string
  message?: string
  mode?: string
  persona?: string
}) {
  return createEngagement({
    goal: body.goal || body.message || "",
    mode: "interactive",
    plan_strategy: "declarative",
    input: body.persona ? { persona: body.persona } : {},
  }).then((engagement) => ({
    run_context: {
      context_id: engagement.engagement_id,
      kind: "job",
      tenant_id: "default",
      correlation_key: engagement.engagement_id,
    },
    result: {
      engagement_id: engagement.engagement_id,
      status: engagement.status,
      job_ids: engagement.job_ids,
    },
  }))
}

export function runStep(runId: string, body: { message: string; mode?: string }) {
  return request<RunResponse>(`/runs/${runId}/steps`, {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export function getRun(runId: string) {
  return request<{ run_context: RunResponse["run_context"]; state: Record<string, unknown> | null }>(
    `/runs/${runId}`,
  )
}

export function approvePlan(
  runId: string,
  body: { decision: "approve" | "reject" | "edit"; actor?: string },
) {
  return request<RunResponse>(`/runs/${runId}/approve-plan`, {
    method: "POST",
    body: JSON.stringify(body),
  })
}
