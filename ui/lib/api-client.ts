import { getClientSessionToken } from "@/lib/auth/session"
import type { FollowUpListResult, FollowUpSendResult } from "@/lib/follow-up"

const PROXY_BASE = "/api/egregore"
const UPSTREAM_BASE =
  process.env.EGREGORE_API_UPSTREAM ??
  (process.env.NODE_ENV === "development" ? "http://127.0.0.1:8080" : "http://egregore-api:8080")

const DEFAULT_API_TIMEOUT_MS = 20_000

export function apiRequestTimeoutMs(): number {
  const raw = process.env.NEXT_PUBLIC_EGREGORE_API_TIMEOUT_MS
  if (!raw) {
    return DEFAULT_API_TIMEOUT_MS
  }
  const parsed = Number.parseInt(raw, 10)
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return DEFAULT_API_TIMEOUT_MS
  }
  return parsed
}

/** AbortSignal for the initial SSE HTTP connect (clear after response headers). */
export function createApiConnectTimeout(): { signal: AbortSignal; clear: () => void } {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), apiRequestTimeoutMs())
  return {
    signal: controller.signal,
    clear: () => clearTimeout(timer),
  }
}

/** Merge abort signals (connect timeout, user abort, unmount). */
export function mergeAbortSignals(signals: AbortSignal[]): AbortSignal | undefined {
  const active = signals.filter(Boolean)
  if (active.length === 0) {
    return undefined
  }
  if (active.length === 1) {
    return active[0]
  }
  if (typeof AbortSignal.any === "function") {
    return AbortSignal.any(active)
  }
  const controller = new AbortController()
  for (const signal of active) {
    if (signal.aborted) {
      controller.abort()
      return controller.signal
    }
    signal.addEventListener("abort", () => controller.abort(), { once: true })
  }
  return controller.signal
}

function mapFetchError(exc: unknown): never {
  if (exc instanceof ApiError) {
    throw exc
  }
  if (exc instanceof DOMException && (exc.name === "TimeoutError" || exc.name === "AbortError")) {
    throw new ApiError("API request timed out", 408)
  }
  throw exc
}

function resolveApiBase(): string {
  if (typeof window !== "undefined") {
    return PROXY_BASE
  }
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

export function isNotFoundError(err: unknown): boolean {
  return err instanceof ApiError && err.status === 404
}

/** Canonical operator unit id: work_order_id = engagement_id = investigation_id. */
export function resolveOperatorUnitId(unit: {
  work_order_id?: string
  engagement_id?: string
  investigation_id?: string
}): string {
  return unit.work_order_id ?? unit.engagement_id ?? unit.investigation_id ?? ""
}

/** Default planner profile from seed catalog (multipurpose runtime; UI does not expose picker yet). */
export const DEFAULT_PROFILE_ID = "cybersec-soc"

export function apiAuthHeaders(): Record<string, string> {
  const result: Record<string, string> = {}
  const envToken = process.env.NEXT_PUBLIC_EGREGORE_API_TOKEN
  if (envToken) {
    result.Authorization = `Bearer ${envToken}`
    return result
  }

  if (typeof window !== "undefined") {
    const sessionToken = getClientSessionToken()
    if (sessionToken) {
      result.Authorization = `Bearer ${sessionToken}`
    }
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
  const timeoutSignal = AbortSignal.timeout(apiRequestTimeoutMs())
  const signal = mergeAbortSignals([init?.signal, timeoutSignal].filter(Boolean) as AbortSignal[])

  let response: Response
  try {
    response = await fetch(`${resolveApiBase()}${path}`, {
      ...init,
      headers: {
        ...headers(),
        ...(init?.headers ?? {}),
      },
      cache: "no-store",
      signal,
    })
  } catch (exc) {
    mapFetchError(exc)
  }

  if (!response.ok) {
    const detail = await response.text()
    throw new ApiError(detail || response.statusText, response.status)
  }
  if (response.status === 204) {
    return undefined as T
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

export type HealthResponse = {
  status: string
  features: {
    stream_agent_output: boolean
    stream_agent_tools: boolean
  }
}

export function getHealth() {
  return request<HealthResponse>("/health")
}

export type InfraHealthResponse = {
  status: string
  queue: { backend: string; depth: number | null }
  egress: { backend: string }
  bus_transport: { backend: string }
  workers_hint: "ok" | "backlog" | "processing" | string
  running_jobs: number
}

export function getHealthInfra() {
  return request<InfraHealthResponse>("/health/infra")
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
  latest_phase?: string | null
  job_ids: string[]
  playbook_id?: string
  reason?: string
  goal?: string
  completed_personas?: string[]
  failed_personas?: string[]
  planner_plan?: string[] | null
  planner_status?: string | null
  planner_rationale?: string
  planner_error?: string
  planner_sub_goals?: Record<string, string>
  planner_depends_on?: Record<string, string[]>
  findings_summary?: Record<string, unknown>[]
  execution_mode?: string | null
  synthesis_persona?: string | null
  synthesis_status?: string | null
  final_report?: Record<string, unknown> | null
  updated_at?: string
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

export type WorkOrderSummary = EngagementSummary & {
  work_order_id?: string
  profile_id?: string
  intake?: Record<string, unknown>
}

export function createWorkOrder(body: {
  goal?: string
  profile_id?: string
  domain_id?: string
  intake?: Record<string, unknown>
  mode?: string
  plan_strategy?: string
  tenant_id?: string
  correlation_id?: string
}) {
  return request<WorkOrderSummary>("/v1/work-orders", {
    method: "POST",
    body: JSON.stringify(body),
  }).catch(async (err) => {
    if (!isNotFoundError(err)) {
      throw err
    }
    const goal =
      (body.goal ?? "").trim() ||
      String(body.intake?.goal ?? "").trim()
    const input = body.intake ? { ...body.intake, intake: body.intake } : undefined
    const eng = await createEngagement({
      goal,
      profile_id: body.profile_id,
      domain_id: body.domain_id,
      mode: body.mode,
      plan_strategy: body.plan_strategy,
      tenant_id: body.tenant_id,
      correlation_id: body.correlation_id,
      input,
    })
    return {
      ...eng,
      work_order_id: eng.engagement_id,
      profile_id: body.profile_id,
      intake: body.intake ?? {},
    } satisfies WorkOrderSummary
  })
}

export async function getWorkOrder(workOrderId: string, tenantId = "default") {
  try {
    return await request<WorkOrderSummary>(
      `/v1/work-orders/${encodeURIComponent(workOrderId)}?tenant_id=${encodeURIComponent(tenantId)}`,
    )
  } catch (err) {
    if (isNotFoundError(err)) {
      return null
    }
    throw err
  }
}

export function listWorkOrders(tenantId = "default", limit = 20) {
  return request<{ work_orders: WorkOrderSummary[] }>(
    `/v1/work-orders?tenant_id=${encodeURIComponent(tenantId)}&limit=${limit}`,
  )
}

export function sendWorkOrderFollowUp(
  workOrderId: string,
  body: { message: string; tenant_id?: string; mode?: "auto" | "qa" | "orchestrate" | "plan" },
) {
  const message = body.message.trim()
  if (!message) {
    throw new ApiError("Follow-up message is empty", 400)
  }
  return request<FollowUpSendResult>(
    `/v1/work-orders/${encodeURIComponent(workOrderId)}/follow-ups`,
    {
      method: "POST",
      body: JSON.stringify({
        message,
        tenant_id: body.tenant_id ?? "default",
        mode: body.mode ?? "auto",
        enqueue: true,
      }),
    },
  ).catch((err) => {
    if (!isNotFoundError(err)) {
      throw err
    }
    return sendInvestigationFollowUp(workOrderId, body)
  })
}

export function listWorkOrderFollowUps(workOrderId: string, tenantId = "default") {
  return request<FollowUpListResult>(
    `/v1/work-orders/${encodeURIComponent(workOrderId)}/follow-ups?tenant_id=${encodeURIComponent(tenantId)}`,
  ).catch((err) => {
    if (!isNotFoundError(err)) {
      throw err
    }
    return listInvestigationFollowUps(workOrderId, tenantId)
  })
}

/** POST operator follow-up for a closed engagement. */
export function sendInvestigationFollowUp(
  investigationId: string,
  body: { message: string; tenant_id?: string; mode?: "auto" | "qa" | "orchestrate" | "plan" },
) {
  const message = body.message.trim()
  if (!message) {
    throw new ApiError("Follow-up message is empty", 400)
  }
  return request<FollowUpSendResult>(
    `/v1/engagements/${encodeURIComponent(investigationId)}/follow-ups`,
    {
      method: "POST",
      body: JSON.stringify({
        message,
        tenant_id: body.tenant_id ?? "default",
        mode: body.mode ?? "auto",
        enqueue: true,
      }),
    },
  )
}

export function listInvestigationFollowUps(investigationId: string, tenantId = "default") {
  return request<FollowUpListResult>(
    `/v1/engagements/${encodeURIComponent(investigationId)}/follow-ups?tenant_id=${encodeURIComponent(tenantId)}`,
  )
}

export function getEngagement(engagementId: string, tenantId = "default") {
  return request<EngagementSummary>(
    `/v1/engagements/${encodeURIComponent(engagementId)}?tenant_id=${encodeURIComponent(tenantId)}`,
  )
}

export type EngagementStreamEvent = {
  type?: string
  phase?: string
  ts?: string
  payload?: Record<string, unknown>
}

export function getEngagementEvents(engagementId: string, tenantId = "default") {
  return request<EngagementStreamEvent[]>(
    `/v1/engagements/${encodeURIComponent(engagementId)}/events?tenant_id=${encodeURIComponent(tenantId)}`,
  )
}

export type MemoryEntry = {
  id: string
  investigation_id: string
  source_agent: string
  source_job_id: string
  memory_type: string
  trust_score: number
  content: string
  content_parsed: Record<string, unknown> | null
  created_at: string
}

export function getEngagementMemory(
  engagementId: string,
  opts: { agent?: string; memoryType?: string; limit?: number; tenantId?: string } = {},
) {
  const params = new URLSearchParams({ tenant_id: opts.tenantId ?? "default" })
  if (opts.agent) params.set("agent", opts.agent)
  if (opts.memoryType) params.set("memory_type", opts.memoryType)
  if (opts.limit) params.set("limit", String(opts.limit))
  return request<{ entries: MemoryEntry[] }>(
    `/v1/engagements/${encodeURIComponent(engagementId)}/memory?${params}`,
  )
}

export function listTenantMemory(
  opts: { tenantId?: string; agent?: string; limit?: number } = {},
) {
  const params = new URLSearchParams({ tenant_id: opts.tenantId ?? "default" })
  if (opts.agent) params.set("agent", opts.agent)
  if (opts.limit) params.set("limit", String(opts.limit))
  return request<{ entries: MemoryEntry[] }>(`/v1/memory?${params}`)
}

export function promoteEngagementPlan(
  engagementId: string,
  body: { plan_id: string; activate?: boolean },
  tenantId = "default",
) {
  return request<Record<string, unknown>>(
    `/v1/engagements/${encodeURIComponent(engagementId)}/promote-plan?tenant_id=${encodeURIComponent(tenantId)}`,
    { method: "POST", body: JSON.stringify(body) },
  )
}

export function engagementStreamUrl(engagementId: string, tenantId = "default") {
  const params = new URLSearchParams({ tenant_id: tenantId })
  return `${PROXY_BASE}/v1/engagements/${encodeURIComponent(engagementId)}/stream?${params}`
}

export function subscribeEngagementStream(
  engagementId: string,
  onEvent: (event: EngagementStreamEvent) => void,
  tenantId = "default",
): () => void {
  const source = new EventSource(engagementStreamUrl(engagementId, tenantId))
  source.onmessage = (message) => {
    try {
      onEvent(JSON.parse(message.data) as EngagementStreamEvent)
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
  failed_personas?: string[]
  updated_at?: string
}

export type InvestigationDetail = InvestigationSummary & {
  planner_plan: string[] | null
  planner_status?: string | null
  planner_rationale?: string
  planner_error?: string
  planner_sub_goals?: Record<string, string>
  planner_depends_on?: Record<string, string[]>
  findings_summary: Record<string, unknown>[]
  final_report?: Record<string, unknown> | null
  latest_phase?: string | null
  execution_mode?: string | null
  synthesis_persona?: string | null
  work_order_id?: string
  profile_id?: string
  intake?: Record<string, unknown>
}

function mapWorkOrderSummary(wo: WorkOrderSummary, tenantId: string): InvestigationDetail {
  const id = wo.work_order_id ?? wo.engagement_id
  return {
    investigation_id: id,
    work_order_id: wo.work_order_id ?? id,
    tenant_id: tenantId,
    goal: wo.goal ?? "",
    status: wo.status,
    completed_personas: wo.completed_personas ?? [],
    failed_personas: wo.failed_personas ?? [],
    planner_plan: wo.planner_plan ?? null,
    planner_status: wo.planner_status ?? null,
    planner_rationale: wo.planner_rationale ?? "",
    planner_error: wo.planner_error ?? "",
    planner_sub_goals: wo.planner_sub_goals ?? {},
    planner_depends_on: wo.planner_depends_on ?? {},
    findings_summary: wo.findings_summary ?? [],
    final_report: wo.final_report ?? null,
    latest_phase: wo.latest_phase ?? null,
    execution_mode: wo.execution_mode ?? null,
    synthesis_persona: wo.synthesis_persona ?? null,
    profile_id: wo.profile_id,
    intake: wo.intake ?? {},
  }
}

function mapEngagementToInvestigation(eng: EngagementSummary, tenantId: string): InvestigationDetail {
  return {
    investigation_id: eng.engagement_id,
    tenant_id: tenantId,
    goal: eng.goal ?? "",
    status: eng.status,
    completed_personas: eng.completed_personas ?? [],
    failed_personas: eng.failed_personas ?? [],
    planner_plan: eng.planner_plan ?? null,
    planner_status: eng.planner_status ?? null,
    planner_rationale: eng.planner_rationale ?? "",
    planner_error: eng.planner_error ?? "",
    planner_sub_goals: eng.planner_sub_goals ?? {},
    planner_depends_on: eng.planner_depends_on ?? {},
    findings_summary: eng.findings_summary ?? [],
    final_report: eng.final_report ?? null,
    latest_phase: eng.latest_phase ?? null,
    execution_mode: eng.execution_mode ?? null,
    synthesis_persona: eng.synthesis_persona ?? null,
  }
}

export type JobSummary = {
  job_id: string
  persona: string
  status: string
  session_id: string
  correlation_id: string
  event_id: string
  follow_up_id?: string | null
}

export function listWorkOrdersAsInvestigations(tenantId = "default", limit = 50) {
  return listWorkOrders(tenantId, limit).then((data) => ({
    investigations: data.work_orders
      .map((wo) => {
        const id = resolveOperatorUnitId(wo)
        return {
          investigation_id: id,
          tenant_id: tenantId,
          goal: wo.goal ?? "",
          status: wo.status,
          completed_personas: wo.completed_personas ?? [],
          failed_personas: wo.failed_personas ?? [],
          updated_at: wo.updated_at,
        } satisfies InvestigationSummary
      })
      .sort(
        (left, right) =>
          investigationUpdatedTimestamp(right.updated_at) -
          investigationUpdatedTimestamp(left.updated_at),
      ),
  }))
}

export async function listInvestigations(tenantId = "default", limit = 50) {
  try {
    return await listWorkOrdersAsInvestigations(tenantId, limit)
  } catch (err) {
    if (!isNotFoundError(err)) {
      throw err
    }
    return listInvestigationsLegacy(tenantId, limit)
  }
}

/** @deprecated use listWorkOrdersAsInvestigations */
export function listInvestigationsLegacy(tenantId = "default", limit = 50) {
  return request<{ engagements: EngagementSummary[] }>(
    `/v1/engagements?tenant_id=${encodeURIComponent(tenantId)}&limit=${limit}`,
  ).then((data) => ({
    investigations: data.engagements
      .map((eng) => ({
        investigation_id: eng.engagement_id,
        tenant_id: tenantId,
        goal: eng.goal ?? "",
        status: eng.status,
        completed_personas: eng.completed_personas ?? [],
        failed_personas: eng.failed_personas ?? [],
        updated_at: eng.updated_at,
      }))
      .sort(
        (left, right) =>
          investigationUpdatedTimestamp(right.updated_at) -
          investigationUpdatedTimestamp(left.updated_at),
      ),
  }))
}

function investigationUpdatedTimestamp(value?: string): number {
  if (!value) return 0
  const ts = Date.parse(value)
  return Number.isNaN(ts) ? 0 : ts
}

export async function getWorkOrderDetail(workOrderId: string, tenantId = "default") {
  const [workOrder, engagement] = await Promise.all([
    getWorkOrder(workOrderId, tenantId),
    getEngagement(workOrderId, tenantId).catch((err) => {
      if (isNotFoundError(err)) {
        return null
      }
      throw err
    }),
  ])
  if (!workOrder && !engagement) {
    throw new ApiError("work order not found", 404)
  }
  const base = engagement
    ? mapEngagementToInvestigation(engagement, tenantId)
    : mapWorkOrderSummary(workOrder!, tenantId)
  const unitId = resolveOperatorUnitId({
    work_order_id: workOrder?.work_order_id ?? workOrder?.engagement_id,
    engagement_id: engagement?.engagement_id,
    investigation_id: workOrderId,
  })
  return {
    ...base,
    investigation_id: unitId,
    work_order_id: workOrder?.work_order_id ?? engagement?.engagement_id ?? workOrderId,
    profile_id: workOrder?.profile_id ?? base.profile_id,
    intake: workOrder?.intake ?? {},
  }
}

export function getInvestigation(investigationId: string, tenantId = "default") {
  return getWorkOrderDetail(investigationId, tenantId)
}

/** @deprecated prefer getWorkOrderDetail */
export function getInvestigationFromEngagement(investigationId: string, tenantId = "default") {
  return getEngagement(investigationId, tenantId).then((eng) =>
    mapEngagementToInvestigation(eng, tenantId),
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
  return `${PROXY_BASE}/status/stream`
}

export type CatalogAgent = {
  name: string
  description?: string
  role?: string
  tools?: string[]
  skills?: string[]
  profile_id?: string
  version?: number
  version_tag?: string
  enabled?: boolean
  empirical_trust?: number
}

export type CatalogAgentDetail = CatalogAgent & {
  system_prompt?: string
  system_prompt_digest?: string
}

export type CatalogSkill = {
  skill_id: string
  name?: string
  description?: string
  body?: string
  version?: number
  enabled?: boolean
  approval_status?: string
}

export type CatalogTool = {
  tool_id: string
  name?: string
  description?: string
  risk_tier?: string
  enabled?: boolean
}

export type CatalogPlan = {
  plan_id: string
  name?: string
  description?: string
  personas?: string[]
  active?: boolean
}

export function listCatalogAgents() {
  return request<{ agents: CatalogAgent[] }>("/catalog/agents")
}

export function getCatalogAgent(name: string) {
  return request<CatalogAgentDetail>(`/catalog/agents/${encodeURIComponent(name)}`)
}

export function putCatalogAgent(name: string, body: Record<string, unknown>) {
  return request<CatalogAgent>(`/catalog/agents/${encodeURIComponent(name)}`, {
    method: "PUT",
    body: JSON.stringify(body),
  })
}

export function listCatalogSkills() {
  return request<{ skills: CatalogSkill[] }>("/catalog/skills")
}

export function getCatalogSkill(skillId: string) {
  return request<CatalogSkill>(`/catalog/skills/${encodeURIComponent(skillId)}`)
}

export function putCatalogSkill(skillId: string, body: Record<string, unknown>) {
  return request<CatalogSkill>(`/catalog/skills/${encodeURIComponent(skillId)}`, {
    method: "PUT",
    body: JSON.stringify(body),
  })
}

export function approveCatalogSkill(skillId: string) {
  return request<CatalogSkill>(`/catalog/skills/${encodeURIComponent(skillId)}/approve`, {
    method: "POST",
  })
}

export function listCatalogTools() {
  return request<{ tools: CatalogTool[] }>("/catalog/tools")
}

export function listCatalogPlans() {
  return request<{ plans: CatalogPlan[] }>("/catalog/plans")
}

export function reloadCatalog() {
  return request<{ status: string }>("/catalog/reload", { method: "POST" })
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

