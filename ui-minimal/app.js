"use strict";

const STORAGE_API = "egregore_minimal_api_base";
const STORAGE_TOKEN = "egregore_minimal_api_token";
const STORAGE_LANGFUSE = "egregore_minimal_langfuse_host";
const DEFAULT_API = "http://127.0.0.1:8080";
const DEFAULT_LANGFUSE = "http://localhost:3001";
const CHAT_THROTTLE_MS = 50;

const $ = (sel) => document.querySelector(sel);

function apiBase() {
  if (window.location.port === "30300") {
    return window.location.origin;
  }
  return ($("#api-base").value || DEFAULT_API).replace(/\/$/, "");
}

function langfuseHost() {
  return ($("#langfuse-host").value || DEFAULT_LANGFUSE).replace(/\/$/, "");
}

function authHeaders() {
  const token = $("#api-token").value.trim();
  const headers = { "Content-Type": "application/json" };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request(path, init = {}) {
  const response = await fetch(`${apiBase()}${path}`, {
    ...init,
    headers: { ...authHeaders(), ...(init.headers || {}) },
    cache: "no-store",
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new ApiError(detail || response.statusText, response.status);
  }
  if (response.status === 204) {
    return null;
  }
  return response.json();
}

function createEngagement(goal) {
  return request("/v1/engagements", {
    method: "POST",
    body: JSON.stringify({
      goal,
      plan_strategy: "meta_llm",
      mode: "async",
    }),
  });
}

function listEngagements(tenantId = "default", limit = 20) {
  return request(
    `/v1/engagements?tenant_id=${encodeURIComponent(tenantId)}&limit=${limit}`,
  );
}

function getEngagement(id, tenantId = "default") {
  return request(
    `/v1/engagements/${encodeURIComponent(id)}?tenant_id=${encodeURIComponent(tenantId)}`,
  );
}

function getEngagementEvents(id, tenantId = "default") {
  return request(
    `/v1/engagements/${encodeURIComponent(id)}/events?tenant_id=${encodeURIComponent(tenantId)}`,
  );
}

function getInvestigationJobs(id, tenantId = "default") {
  return request(
    `/investigations/${encodeURIComponent(id)}/jobs?tenant_id=${encodeURIComponent(tenantId)}`,
  );
}

function getEngagementMemory(id, { agent, memoryType, limit, tenantId } = {}) {
  const params = new URLSearchParams({ tenant_id: tenantId || "default" });
  if (agent) params.set("agent", agent);
  if (memoryType) params.set("memory_type", memoryType);
  if (limit) params.set("limit", String(limit));
  return request(`/v1/engagements/${encodeURIComponent(id)}/memory?${params}`);
}

function listCatalogAgents() {
  return request("/catalog/agents");
}

function getCatalogAgent(name) {
  return request(`/catalog/agents/${encodeURIComponent(name)}`);
}

function listCatalogTools() {
  return request("/catalog/tools");
}

function listCatalogSkills() {
  return request("/catalog/skills");
}

function listCatalogPlans() {
  return request("/catalog/plans");
}

function getCatalogSkill(skillId) {
  return request(`/catalog/skills/${encodeURIComponent(skillId)}`);
}

function putCatalogSkill(skillId, body) {
  return request(`/catalog/skills/${encodeURIComponent(skillId)}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

function approveCatalogSkill(skillId) {
  return request(`/catalog/skills/${encodeURIComponent(skillId)}/approve`, { method: "POST" });
}

function putCatalogAgent(name, body) {
  return request(`/catalog/agents/${encodeURIComponent(name)}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

function reloadCatalog() {
  return request("/catalog/reload", { method: "POST" });
}

function listTenantMemory({ tenantId = "default", agent, limit } = {}) {
  const params = new URLSearchParams({ tenant_id: tenantId });
  if (agent) params.set("agent", agent);
  if (limit) params.set("limit", String(limit));
  return request(`/v1/memory?${params}`);
}

function promoteEngagementPlan(engagementId, body, tenantId = "default") {
  return request(
    `/v1/engagements/${encodeURIComponent(engagementId)}/promote-plan?tenant_id=${encodeURIComponent(tenantId)}`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

function hasOperatorToken() {
  return Boolean($("#api-token").value.trim());
}

function listPendingApprovals() {
  return request("/approvals/pending");
}

function resumeJob(jobId, body) {
  return request(`/jobs/${encodeURIComponent(jobId)}/resume`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

function getStatus() {
  return request("/status");
}

async function loadFeatures() {
  try {
    const response = await fetch(`${apiBase()}/health`, { cache: "no-store" });
    if (response.ok) {
      const data = await response.json();
      features.streamAgentOutput = Boolean(data.features?.stream_agent_output);
      features.streamAgentTools = Boolean(data.features?.stream_agent_tools);
    }
  } catch {
    // keep defaults
  }
  applyFeatureGate();
}

function applyFeatureGate() {
  const responseSection = $("#detail-response-section");
  const actionHeader = $("#detail-jobs-action-header");
  if (responseSection) {
    responseSection.classList.toggle("hidden", !features.streamAgentOutput);
  }
  if (actionHeader) {
    actionHeader.classList.toggle("hidden", !features.streamAgentOutput);
  }
}

function plannerJobId(engagementId) {
  return `planner:${engagementId}`;
}

function egressSummary(event) {
  const phase = event.phase || event.type || "event";
  const payload = event.payload || {};
  const parts = [phase];
  if (payload.persona) parts.push(payload.persona);
  if (payload.job_id) parts.push(payload.job_id);
  if (payload.planner_error) parts.push(payload.planner_error);
  if (payload.tool_name) parts.push(payload.tool_name);
  if (payload.skill_name) parts.push(`skill:${payload.skill_name}`);
  if (event.type === "assistant_delta" && payload.delta) {
    const snippet = String(payload.delta);
    parts.push(`"${snippet.slice(0, 40)}${snippet.length > 40 ? "…" : ""}"`);
    if (payload.seq != null) parts.push(`seq:${payload.seq}`);
  }
  if (event.type === "reasoning_delta" && payload.current_situation) {
    parts.push(String(payload.current_situation).slice(0, 48));
  }
  const verdict = payload.verdict;
  if (verdict && typeof verdict === "object") {
    if (typeof verdict.passed === "boolean") parts.push(verdict.passed ? "passed" : "failed");
    const issues = verdict.issues_detected;
    if (Array.isArray(issues) && issues.length) parts.push(`issues:${issues.length}`);
  }
  if (payload.summary && typeof payload.summary === "string") {
    const snippet = payload.summary.slice(0, 48);
    if (snippet) parts.push(snippet);
  }
  if (payload.error) parts.push(String(payload.error).slice(0, 48));
  return parts.join(" · ");
}

/** Mirror of cys_core/domain/parsing/json_text.py */
function parseJsonText(text) {
  if (typeof text !== "string" || !text.trim()) return null;
  try {
    const parsed = JSON.parse(text);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) return parsed;
  } catch {
    // try fenced block below
  }
  const stripped = text.trim();
  if (!stripped.startsWith("```")) return null;
  const lines = stripped.split("\n");
  if (lines[0].startsWith("```")) lines.shift();
  if (lines.length && lines[lines.length - 1].trim() === "```") lines.pop();
  const fenced = lines.join("\n").trim();
  try {
    const parsed = JSON.parse(fenced);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) return parsed;
  } catch {
    return null;
  }
  return null;
}

function normalizeFindingPayload(input) {
  if (input == null) return {};
  if (typeof input === "string") {
    const parsed = parseJsonText(input);
    return parsed || { raw_response: input };
  }
  if (typeof input !== "object") return {};
  if (input.finding != null) {
    const inner = normalizeFindingPayload(input.finding);
    if (inner && Object.keys(inner).length) return inner;
  }
  if (input.data != null) {
    const inner = normalizeFindingPayload(input.data);
    if (inner && Object.keys(inner).length) return inner;
  }
  if (input.content_parsed && typeof input.content_parsed === "object") return input.content_parsed;
  if (typeof input.content === "string") {
    const parsed = parseJsonText(input.content);
    if (parsed) return parsed;
  }
  if (input.raw_response) {
    const parsed = parseJsonText(String(input.raw_response));
    if (parsed) return { ...parsed, _raw_response: input.raw_response };
  }
  return input;
}

function findingBody(finding) {
  return normalizeFindingPayload(finding);
}

function asStringList(value) {
  if (!Array.isArray(value)) return [];
  return value.filter((item) => typeof item === "string" && item.length > 0);
}

function formatEvidenceItem(item) {
  if (typeof item === "string") return item;
  if (item && typeof item === "object") {
    if (item.obs_id) {
      const excerpt = item.excerpt ? `: ${item.excerpt}` : "";
      return `${item.obs_id}${excerpt}`;
    }
    const source = item.source ? `[${item.source}] ` : "";
    const desc = item.description || item.summary || JSON.stringify(item);
    const ref = item.reference ? ` (${item.reference})` : "";
    return `${source}${desc}${ref}`;
  }
  return String(item);
}

function telemetryBadge(level) {
  if (!level || level === "rich") return "";
  const label = level === "sparse" ? "Low telemetry" : "Metadata only";
  return `<span class="badge badge-warn">${escapeHtml(label)}</span>`;
}

function formatFindingHtml(finding) {
  let data = findingBody(finding);
  if (!data || typeof data !== "object") return '<p class="muted">—</p>';
  if (typeof finding === "string") {
    const parsed = parseJsonText(finding);
    if (parsed) data = parsed;
    else return `<pre>${escapeHtml(finding)}</pre>`;
  }
  if (data.raw_response && !data.summary && !data.finding && !data.message && !data.analysis) {
    const parsed = parseJsonText(String(data.raw_response));
    if (parsed) data = { ...parsed, _raw_response: data.raw_response };
    else return `<pre class="finding-raw">${escapeHtml(String(data.raw_response))}</pre>`;
  }

  const sections = [];
  const topic = data.topic;
  const summary = data.summary || data.finding || data.message || data.analysis;
  const risk = data.risk_level || data.severity || data.priority;
  const confidence = typeof data.confidence === "number" ? data.confidence : null;
  const recommendations =
    asStringList(data.recommendations) ||
    asStringList(data.recommended_actions) ||
    asStringList(data.recommended_remediation);
  const timeline = asStringList(data.timeline);
  const mitreTactics = asStringList(data.mitre_tactics);
  const mitreTechniques = asStringList(data.mitre_techniques);
  const references = asStringList(data.references);
  const evidence = Array.isArray(data.evidence) ? data.evidence : [];
  const dataGaps = Array.isArray(data.data_gaps) ? data.data_gaps : [];
  const telemetryLevel = data.telemetry_level || "";
  const affectedAssets = Array.isArray(data.affected_assets) ? data.affected_assets : asStringList(data.affected_assets);

  if (topic) sections.push(`<div class="finding-section"><h4>Topic</h4><p>${escapeHtml(topic)}</p></div>`);
  if (summary) {
    sections.push(`<div class="finding-section"><h4>Summary</h4><p class="finding-summary">${escapeHtml(summary)}</p></div>`);
  }
  if (risk || confidence !== null || telemetryLevel) {
    const meta = [
      risk ? `Risk: ${risk}` : "",
      confidence !== null ? `Confidence: ${(confidence * 100).toFixed(0)}%` : "",
      telemetryLevel ? `Telemetry: ${telemetryLevel}` : "",
    ]
      .filter(Boolean)
      .join(" · ");
    sections.push(
      `<div class="finding-section finding-meta">${telemetryBadge(telemetryLevel)} ${escapeHtml(meta)}</div>`,
    );
  }
  if (mitreTactics.length || mitreTechniques.length) {
    const lines = [];
    if (mitreTactics.length) lines.push(`Tactics: ${mitreTactics.join(", ")}`);
    if (mitreTechniques.length) lines.push(`Techniques: ${mitreTechniques.join(", ")}`);
    sections.push(`<div class="finding-section"><h4>MITRE</h4><p>${escapeHtml(lines.join(" · "))}</p></div>`);
  }
  if (timeline.length) {
    sections.push(
      `<div class="finding-section"><h4>Timeline</h4><ul>${timeline.map((t) => `<li>${escapeHtml(t)}</li>`).join("")}</ul></div>`,
    );
  }
  if (evidence.length) {
    sections.push(
      `<div class="finding-section"><h4>Evidence</h4><ul>${evidence.map((e) => `<li>${escapeHtml(formatEvidenceItem(e))}</li>`).join("")}</ul></div>`,
    );
  }
  if (dataGaps.length) {
    sections.push(
      `<div class="finding-section"><h4>Data gaps</h4><ul>${dataGaps
        .map((gap) => {
          if (typeof gap === "string") return `<li>${escapeHtml(gap)}</li>`;
          const field = gap.field || "unknown";
          const remediation = gap.remediation ? ` — ${gap.remediation}` : "";
          return `<li><code>${escapeHtml(field)}</code>${escapeHtml(remediation)}</li>`;
        })
        .join("")}</ul></div>`,
    );
  }
  if (affectedAssets.length) {
    sections.push(
      `<div class="finding-section"><h4>Affected assets</h4><ul>${affectedAssets
        .map((a) => `<li>${escapeHtml(typeof a === "string" ? a : JSON.stringify(a))}</li>`)
        .join("")}</ul></div>`,
    );
  }
  if (recommendations.length) {
    sections.push(
      `<div class="finding-section"><h4>Recommendations</h4><ul>${recommendations
        .map((r) => `<li>${escapeHtml(r)}</li>`)
        .join("")}</ul></div>`,
    );
  }
  if (references.length) {
    sections.push(
      `<div class="finding-section"><h4>References</h4><ul>${references.map((r) => `<li>${escapeHtml(r)}</li>`).join("")}</ul></div>`,
    );
  }
  if (sections.length >= 2) return sections.join("");
  const body = sections.length ? sections.join("") : "";
  const rawJson = `<details class="finding-raw-collapsible"><summary>Raw JSON</summary><pre class="finding-raw">${escapeHtml(
    JSON.stringify(data, null, 2),
  )}</pre></details>`;
  return body + rawJson;
}

function meaningfulFieldCount(data) {
  if (!data || typeof data !== "object") return 0;
  let count = 0;
  for (const [key, value] of Object.entries(data)) {
    if (key.startsWith("_")) continue;
    if (typeof value === "string" && value.trim()) count += 1;
    else if (Array.isArray(value) && value.length) count += 1;
    else if (typeof value === "number" && value !== 0) count += 1;
  }
  return count;
}

function formatFinding(finding) {
  const data = findingBody(finding);
  if (!data || typeof data !== "object") return "—";
  if (data.raw_response) {
    const parsed = parseJsonText(String(data.raw_response));
    if (parsed) {
      const summary = parsed.summary || parsed.finding || parsed.message || parsed.analysis;
      if (summary) return String(summary);
      return JSON.stringify(parsed, null, 2);
    }
    return String(data.raw_response);
  }
  if (meaningfulFieldCount(data) > 1) return JSON.stringify(data, null, 2);
  const summary = data.summary || data.finding || data.message;
  if (summary) return String(summary);
  return JSON.stringify(data, null, 2);
}

function deriveEngagementView(eng, jobs) {
  const allTerminal =
    jobs.length > 0 &&
    jobs.every((j) => ["completed", "failed"].includes((j.status || "").toLowerCase()));
  const failedSet = new Set(eng.failed_personas || []);
  const completedPersonas = eng.completed_personas?.length
    ? eng.completed_personas.filter((p) => !failedSet.has(p))
    : jobs.filter((j) => (j.status || "").toLowerCase() === "completed").map((j) => j.persona);
  const displayStatus = allTerminal ? "closed" : eng.status;
  return { displayStatus, completedPersonas };
}

function langfuseProject() {
  const defaults = window.EGREGORE_DEFAULTS || {};
  return defaults.langfuseProject || "egregore-dev";
}

function langfuseEngagementUrl(engagementId) {
  const host = langfuseHost();
  const project = langfuseProject();
  const q = encodeURIComponent(`engagement:${engagementId}`);
  return `${host}/project/${encodeURIComponent(project)}/traces?search=${q}`;
}

function formatStatusLabel(status) {
  const s = (status || "").toLowerCase();
  if (s === "closed" || s === "completed" || s.includes("finished")) return "Completed";
  if (s === "failed" || s === "error") return "Failed";
  if (s === "enqueued" || s === "running" || s === "planning") return "Running";
  return status || "—";
}

function statusBadgeClass(status) {
  const s = (status || "").toLowerCase();
  if (s.includes("run") || s.includes("plan") || s.includes("queue") || s.includes("enqueued")) return "running";
  if (s.includes("complete") || s.includes("closed") || s.includes("finished") || s.includes("ready") || s.includes("ok")) {
    return "completed";
  }
  if (s.includes("fail") || s.includes("error")) return "failed";
  return "";
}

function showError(el, message) {
  if (!message) {
    el.classList.add("hidden");
    el.textContent = "";
    return;
  }
  el.textContent = message;
  el.classList.remove("hidden");
}

function setTab(name) {
  document.querySelectorAll("nav.tabs button").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === name);
  });
  document.querySelectorAll("main > .panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `panel-${name}`);
  });
}

let currentDetailId = null;
let currentEngagement = null;
let detailEvents = [];
let detailFindings = [];
let detailJobs = [];
let sseStatus = "idle";
let sseAbort = null;
let detailPollMs = 15000;
let infraHealthCache = null;
let features = { streamAgentOutput: false, streamAgentTools: false };
const seenEventKeys = new Set();
/** @type {Map<string, { persona: string, buffer: string, tools: Array<{name: string, status: string}>, streaming: boolean, flushTimer: number|null }>} */
const chatState = new Map();
let openDrawerJobId = null;
let drawerTab = "transcript";
let catalogKind = "agents";
let catalogRows = [];
let catalogSelectedAgent = null;
let catalogSelectedSkill = null;
let openMemoryAgent = null;
const memoryCache = new Map();

function updateStreamBadge() {
  const badge = $("#stream-badge");
  badge.textContent = `Engagement stream: ${sseStatus}`;
  badge.className = "stream-badge";
  if (sseStatus === "open") badge.classList.add("open");
  if (sseStatus === "error" || sseStatus === "closed") badge.classList.add("error");
}

function eventDedupeKey(event) {
  const payload = event.payload || {};
  const type = event.type || "";
  if (type === "assistant_delta") {
    return [type, payload.job_id || "", payload.seq ?? "", payload.delta || ""].join("|");
  }
  if (type === "reasoning_delta") {
    return [
      type,
      payload.job_id || "",
      payload.plan_status || "",
      (payload.reasoning_steps || []).join(","),
    ].join("|");
  }
  if (type === "assistant_snapshot") {
    return [type, payload.job_id || "", payload.text || ""].join("|");
  }
  if (type === "tool_start" || type === "tool_done" || type === "tool_error") {
    const preview = payload.output_preview ? String(payload.output_preview).slice(0, 64) : "";
    return [
      type,
      payload.job_id || "",
      payload.tool_name || "",
      payload.tool_call_id || "",
      preview,
      payload.error || "",
    ].join("|");
  }
  return [
    type,
    event.phase || "",
    payload.job_id || "",
    payload.persona || "",
    payload.summary || "",
    JSON.stringify(payload.verdict || ""),
  ].join("|");
}

function renderDetailEventsLog() {
  const log = $("#detail-events");
  if (!detailEvents.length) {
    log.textContent = "Waiting for engagement stream…";
    return;
  }
  log.innerHTML = detailEvents
    .map(
      (e) =>
        `<div><span class="ts">${escapeHtml(e.ts || new Date().toISOString())}</span> <strong>${escapeHtml(egressSummary(e))}</strong></div>`,
    )
    .join("");
}

function appendDetailEvent(event) {
  const key = eventDedupeKey(event);
  if (seenEventKeys.has(key)) return false;
  seenEventKeys.add(key);
  detailEvents = [...detailEvents.slice(-199), event];
  renderDetailEventsLog();
  return true;
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function parseSseChunk(chunk, onData) {
  for (const line of chunk.split("\n")) {
    if (line.startsWith("data:")) {
      onData(line.slice(5).trim());
    }
  }
}

function disconnectEngagementStream() {
  if (sseAbort) {
    sseAbort.abort();
    sseAbort = null;
  }
  sseStatus = "idle";
  updateStreamBadge();
}

function eventPayload(event) {
  return event.payload || {};
}

function shouldRefreshOnEvent(event) {
  const type = event.type || "";
  const phase = event.phase || "";
  if (["assistant_done", "job_finished", "job_started", "error", "control", "report"].includes(type)) {
    return true;
  }
  if (type === "status" && phase === "final_report") {
    return true;
  }
  if (
    type === "status" &&
    ["job_started", "job_finished", "error", "planning_done", "planning_error"].includes(phase)
  ) {
    return true;
  }
  return false;
}

function transcriptPlaceholder(state, jobId) {
  if (state?.buffer) return escapeHtml(state.buffer);
  return '<span class="muted">No live tokens — open Finding tab or refresh after job completes.</span>';
}

function hydrateTranscriptFromDetail(eng, jobs) {
  for (const item of eng.findings_summary || []) {
    const jobId = item.job_id;
    if (!jobId) continue;
    const state = ensureChatEntry(jobId, item.persona);
    if (!state.buffer) {
      state.buffer = formatFinding(item.finding || item);
    }
  }
  if (currentDetailId) {
    const pj = plannerJobId(currentDetailId);
    const state = ensureChatEntry(pj, "planner");
    if (!state.buffer && (eng.planner_plan?.length || eng.planner_rationale)) {
      state.buffer = JSON.stringify(
        {
          personas: eng.planner_plan || [],
          rationale: eng.planner_rationale || "",
        },
        null,
        2,
      );
    }
  }
}

function collectEngagementErrors(eng, events) {
  const rows = [];
  const seen = new Set();
  const failed = new Set(eng?.failed_personas || []);
  for (const persona of failed) {
    const key = `persona:${persona}`;
    if (!seen.has(key)) {
      rows.push({ persona, error: "failed", job_id: "", tool: "" });
      seen.add(key);
    }
  }
  for (const event of events || []) {
    const type = event.type || event.phase || "";
    const payload = eventPayload(event);
    if (type === "status" && event.phase === "job_finished" && payload.success === false) {
      const key = `job:${payload.job_id}:${payload.error}`;
      if (!seen.has(key)) {
        rows.push({
          persona: payload.persona || personaFromJobId(payload.job_id || ""),
          error: payload.error || "failed",
          job_id: payload.job_id || "",
          tool: "",
        });
        seen.add(key);
      }
    }
    if (type === "tool_done" && payload.ok === false) {
      const key = `tool:${payload.job_id}:${payload.tool_name}`;
      if (!seen.has(key)) {
        rows.push({
          persona: payload.persona || personaFromJobId(payload.job_id || ""),
          error: payload.output_preview || "tool failed",
          job_id: payload.job_id || "",
          tool: payload.tool_name || "",
        });
        seen.add(key);
      }
    }
  }
  return rows;
}

function renderErrorsPanel(eng) {
  const panel = $("#detail-errors-panel");
  const banner = $("#detail-errors-banner");
  if (!panel || !banner) return;
  if (!eng) {
    panel.classList.add("hidden");
    banner.classList.add("hidden");
    return;
  }
  const plan = eng.planner_plan || [];
  const failed = eng.failed_personas || [];
  const completed = eng.completed_personas || [];
  const specialistCount = plan.length || failed.length + completed.length;
  const failedCount = failed.length;
  const errors = collectEngagementErrors(eng, detailEvents);

  if (specialistCount > 0 && failedCount > 0) {
    banner.textContent = `${failedCount}/${specialistCount} specialists failed — pipeline may still close with consultant synth`;
    banner.classList.remove("hidden");
    banner.classList.toggle("err", failedCount === specialistCount);
    banner.classList.toggle("warn", failedCount < specialistCount);
  } else if (errors.length) {
    banner.textContent = `${errors.length} error(s) recorded`;
    banner.classList.remove("hidden");
    banner.classList.add("warn");
  } else {
    banner.classList.add("hidden");
  }

  if (!errors.length) {
    panel.classList.add("hidden");
    panel.innerHTML = "";
    return;
  }
  panel.classList.remove("hidden");
  panel.innerHTML = `
    <h3 class="detail-subheading">Errors &amp; status</h3>
    <table class="errors-table">
      <thead><tr><th>Persona</th><th>Error</th><th>Job</th><th>Tool</th></tr></thead>
      <tbody>
        ${errors
          .map(
            (row) => `<tr>
          <td>${escapeHtml(row.persona || "—")}</td>
          <td class="err-cell">${escapeHtml(String(row.error || "").slice(0, 200))}</td>
          <td><code>${escapeHtml(row.job_id || "—")}</code></td>
          <td>${escapeHtml(row.tool || "—")}</td>
        </tr>`,
          )
          .join("")}
      </tbody>
    </table>`;
}

function sortChatEntries(entries, eng) {
  const order = [];
  if (eng && currentDetailId) {
    order.push(plannerJobId(currentDetailId));
  }
  for (const persona of eng?.planner_plan || []) {
    const jobId = (eng?.job_ids || []).find((id) => id.startsWith(`${persona}-`));
    if (jobId) order.push(jobId);
  }
  for (const jobId of eng?.job_ids || []) {
    if (!order.includes(jobId)) order.push(jobId);
  }
  const rank = new Map(order.map((id, idx) => [id, idx]));
  return [...entries].sort((a, b) => {
    const ra = rank.has(a[0]) ? rank.get(a[0]) : 999;
    const rb = rank.has(b[0]) ? rank.get(b[0]) : 999;
    return ra - rb;
  });
}

function jobStatusForChat(jobId, eng) {
  const persona = personaFromJobId(jobId);
  if ((eng?.completed_personas || []).includes(persona)) return "completed";
  if ((eng?.failed_personas || []).includes(persona)) return "failed";
  const job = detailJobs.find((j) => j.job_id === jobId);
  if (job?.status) return job.status;
  return "running";
}

function ensureChatEntry(jobId, persona) {
  if (!chatState.has(jobId)) {
    chatState.set(jobId, {
      persona: persona || "—",
      buffer: "",
      turns: [],
      tools: [],
      toolsExpanded: [],
      agentExpanded: true,
      reasoning: null,
      streaming: false,
      jobError: "",
      flushTimer: null,
    });
  }
  return chatState.get(jobId);
}

function matchToolRow(tools, toolName, toolCallId) {
  if (!toolName) return null;
  if (toolCallId) {
    const byId = [...tools].reverse().find((row) => row.tool_call_id === toolCallId);
    if (byId) return byId;
  }
  return [...tools].reverse().find(
    (row) => row.name === toolName || row.name.startsWith(`${toolName} →`),
  );
}

function renderReasoningBlock(reasoning) {
  if (!reasoning) return "";
  const steps = reasoning.reasoning_steps || [];
  if (!reasoning.current_situation && !steps.length && !reasoning.plan_status) {
    return "";
  }
  const stepItems = steps.map((step) => `<li>${escapeHtml(step)}</li>`).join("");
  const status = reasoning.plan_status
    ? `<div class="chat-reasoning-status">${escapeHtml(reasoning.plan_status)}</div>`
    : "";
  return `
    <details class="chat-reasoning">
      <summary>Reasoning</summary>
      ${status}
      ${reasoning.current_situation ? `<div class="chat-reasoning-situation">${escapeHtml(reasoning.current_situation)}</div>` : ""}
      ${stepItems ? `<ol class="chat-reasoning-steps">${stepItems}</ol>` : ""}
    </details>`;
}

function renderToolRows(tools, toolsExpanded) {
  return tools
    .map((tool, idx) => {
      const cls = tool.status === "done" ? "ok" : tool.status === "error" ? "err" : "";
      const preview = tool.output_preview
        ? `<pre class="chat-tool-preview">${escapeHtml(tool.output_preview)}</pre>`
        : "";
      const defaultOpen =
        toolsExpanded[idx] ?? (tool.status === "error" || tool.status === "started");
      const openAttr = defaultOpen ? " open" : "";
      return `<details class="chat-tool ${cls}" data-tool-idx="${idx}"${openAttr}>
        <summary class="chat-tool-row ${cls}">${escapeHtml(tool.name)} — ${escapeHtml(tool.status)}</summary>
        ${preview}
      </details>`;
    })
    .join("");
}

function renderAgentOutcome(jobId, state, eng) {
  const status = jobStatusForChat(jobId, eng);
  if (status === "failed" && state.jobError) {
    return `<div class="chat-agent-error">${escapeHtml(state.jobError)}</div>`;
  }
  const findingHtml = findingHtmlForJob(jobId);
  if (findingHtml && status === "completed") {
    return `<div class="chat-agent-finding">${findingHtml}</div>`;
  }
  return "";
}

function formatBubbleText(text) {
  if (!text) return "";
  let html = escapeHtml(text);
  html = html.replace(/`([^`\n]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
  return html.replace(/\n/g, "<br>");
}

function renderTurnBubbles(state) {
  const parts = (state.turns || []).map(
    (turn) => `<div class="chat-bubble chat-bubble-turn">${formatBubbleText(turn)}</div>`,
  );
  const liveCls = state.streaming
    ? "chat-bubble streaming"
    : state.isControlError
      ? "chat-bubble control-error"
      : "chat-bubble";
  if (state.buffer) {
    parts.push(`<div class="${liveCls}">${formatBubbleText(state.buffer)}</div>`);
  } else if (!parts.length) {
    parts.push(
      `<div class="${liveCls}"><span class="muted">No live tokens — open Finding tab or refresh after job completes.</span></div>`,
    );
  }
  return parts.join("");
}

let currentEngagementGoal = "";

function scheduleChatRender() {
  const el = $("#detail-response");
  if (!el || !features.streamAgentOutput) return;
  if (el._flushTimer) return;
  el._flushTimer = window.setTimeout(() => {
    el._flushTimer = null;
    renderResponseThread();
  }, CHAT_THROTTLE_MS);
}

function renderResponseThread() {
  const el = $("#detail-response");
  if (!el) return;
  const entries = sortChatEntries([...chatState.entries()], currentEngagement);
  if (!entries.length) {
    el.innerHTML = '<span class="muted">Waiting for agent stream…</span>';
    return;
  }
  const goalBlock = currentEngagementGoal
    ? `<div class="chat-user-goal"><span class="muted">Goal</span><div class="chat-bubble chat-bubble-user">${formatBubbleText(currentEngagementGoal)}</div></div>`
    : "";
  el.innerHTML =
    goalBlock +
    entries
      .map(([jobId, state]) => {
        const status = jobStatusForChat(jobId, currentEngagement);
        const toolRows = renderToolRows(state.tools, state.toolsExpanded || []);
        const reasoningBlock = renderReasoningBlock(state.reasoning);
        const viewBtn = features.streamAgentOutput
          ? ` <button type="button" class="btn-link btn-view-job" data-job="${escapeHtml(jobId)}">details</button>`
          : "";
        const bubbleHtml = renderTurnBubbles(state);
        const outcomeHtml = renderAgentOutcome(jobId, state, currentEngagement);
        const sectionOpen = state.agentExpanded !== false && (state.streaming || status === "running");
        const summaryErr = state.jobError ? ` — ${String(state.jobError).slice(0, 80)}` : "";
        return `
        <section class="chat-agent-section" data-chat-job="${escapeHtml(jobId)}">
          <details class="chat-agent-collapse"${sectionOpen ? " open" : ""}>
            <summary class="chat-agent-header">
              <span class="badge ${statusBadgeClass(status)}">${escapeHtml(formatStatusLabel(status))}</span>
              <strong>${escapeHtml(state.persona)}</strong>
              <code>${escapeHtml(jobId)}</code>${viewBtn}
              <span class="chat-agent-summary muted">${escapeHtml(summaryErr)}</span>
            </summary>
            <div class="chat-agent-body">
              ${reasoningBlock}
              ${toolRows ? `<details class="chat-tools-group" open><summary>Tools (${state.tools.length})</summary>${toolRows}</details>` : ""}
              ${bubbleHtml}
              ${outcomeHtml}
            </div>
          </details>
        </section>`;
      })
      .join("");
  el.querySelectorAll(".btn-view-job").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      openJobDetail(btn.dataset.job);
    });
  });
  el.querySelectorAll(".chat-tool").forEach((detailsEl) => {
    detailsEl.addEventListener("toggle", () => {
      const section = detailsEl.closest("[data-chat-job]");
      if (!section) return;
      const jobId = section.dataset.chatJob;
      const state = chatState.get(jobId);
      if (!state) return;
      const idx = Number(detailsEl.dataset.toolIdx);
      if (!state.toolsExpanded) state.toolsExpanded = [];
      state.toolsExpanded[idx] = detailsEl.open;
    });
  });
  el.querySelectorAll(".chat-agent-collapse").forEach((detailsEl) => {
    detailsEl.addEventListener("toggle", () => {
      const jobId = detailsEl.closest("[data-chat-job]")?.dataset.chatJob;
      const state = jobId ? chatState.get(jobId) : null;
      if (state) state.agentExpanded = detailsEl.open;
    });
  });
  el.scrollTop = el.scrollHeight;
}

function resolveControlJobId(type, payload) {
  if (payload.job_id) return payload.job_id;
  const engagementId = currentDetailId || payload.engagement_id || "";
  if (!engagementId) return "";
  if (type === "report") return `coordinator:${engagementId}`;
  if (type === "control" || type === "control_error") return `critic:${engagementId}`;
  return "";
}

function controlEventText(type, payload) {
  if (type === "control_error") return String(payload.error || "control error");
  if (type === "report") return String(payload.summary || "");
  const verdict = payload.verdict;
  if (verdict && typeof verdict === "object") return JSON.stringify(verdict, null, 2);
  return JSON.stringify(payload, null, 2);
}

function handleChatEvent(event) {
  const type = event.type || "";
  const payload = eventPayload(event);
  const controlTypes = ["control", "report", "control_error"];
  let jobId = payload.job_id;
  let persona = payload.persona;
  if (!jobId && controlTypes.includes(type)) {
    jobId = resolveControlJobId(type, payload);
    persona = persona || (type === "report" ? "coordinator" : "critic");
  }
  if (!jobId) return;
  const state = ensureChatEntry(jobId, persona);

  if (controlTypes.includes(type)) {
    state.buffer = controlEventText(type, payload);
    state.streaming = false;
    state.isControlError = type === "control_error";
    scheduleChatRender();
    if (openDrawerJobId === jobId) renderDrawerContent();
    return;
  }

  if (type === "reasoning_delta") {
    state.reasoning = {
      current_situation: payload.current_situation || "",
      plan_status: payload.plan_status || "",
      reasoning_steps: Array.isArray(payload.reasoning_steps) ? payload.reasoning_steps : [],
      task_completed: Boolean(payload.task_completed),
    };
    scheduleChatRender();
    if (openDrawerJobId === jobId) renderDrawerContent();
    return;
  }

  if (type === "assistant_delta") {
    state.buffer += payload.delta || "";
    state.streaming = true;
    scheduleChatRender();
    if (openDrawerJobId === jobId) renderDrawerContent();
    return;
  }
  if (type === "assistant_snapshot") {
    const text = payload.text || "";
    if (text && state.buffer === text) {
      state.streaming = false;
      return;
    }
    if (!state.buffer && text) {
      state.buffer = text;
    }
    state.streaming = false;
    scheduleChatRender();
    if (openDrawerJobId === jobId) renderDrawerContent();
    return;
  }
  if (type === "assistant_done") {
    if (state.buffer) {
      if (!state.turns) state.turns = [];
      state.turns.push(state.buffer);
      state.buffer = "";
    }
    state.streaming = false;
    scheduleChatRender();
    if (openDrawerJobId === jobId) renderDrawerContent();
    return;
  }
  if (type === "status" && event.phase === "job_finished") {
    const err = payload.error || "unknown";
    if (payload.success === false) {
      state.jobError = err;
      if (!state.buffer) {
        if (err.startsWith("tools_not_executed:")) {
          state.buffer = `Tools were planned in JSON but never executed. ${err.slice("tools_not_executed:".length)}`;
        } else if (err.startsWith("empty_finding:")) {
          const gaps = err.slice("empty_finding:".length).replace(/,/g, ", ");
          state.buffer = `Agent finished without a valid finding (missing: ${gaps}).`;
        } else if (err === "empty_finding") {
          state.buffer =
            "Agent finished without a valid finding (model may have refused or returned invalid JSON).";
        } else if (err.startsWith("model_refusal:")) {
          state.buffer = `Model refused: ${err.slice("model_refusal:".length)}`;
        } else {
          state.buffer = `Job failed: ${err}`;
        }
      }
      state.agentExpanded = false;
    } else {
      state.jobError = "";
    }
    state.streaming = false;
    scheduleChatRender();
    renderErrorsPanel(currentEngagement);
    if (openDrawerJobId === jobId) renderDrawerContent();
    return;
  }
  if (type === "tool_start" && features.streamAgentTools) {
    const toolName = payload.tool_name || "tool";
    const toolCallId = payload.tool_call_id || "";
    const label = payload.skill_name ? `${toolName} → ${payload.skill_name}` : toolName;
    state.tools.push({ name: label, status: "started", tool_call_id: toolCallId });
    scheduleChatRender();
    if (openDrawerJobId === jobId) renderDrawerContent();
    return;
  }
  if (type === "skill_loaded") {
    const skill = payload.skill_name || payload.skill || "skill";
    state.tools.push({ name: `load_skill → ${skill}`, status: "done" });
    scheduleChatRender();
    if (openDrawerJobId === jobId) renderDrawerContent();
    return;
  }
  if (type === "tool_done" && features.streamAgentTools) {
    const ok = payload.ok !== false;
    const toolCallId = payload.tool_call_id || "";
    const row = matchToolRow(state.tools, payload.tool_name, toolCallId);
    if (row) {
      row.status = ok ? "done" : "error";
      if (payload.output_preview) row.output_preview = payload.output_preview;
      if (toolCallId) row.tool_call_id = toolCallId;
    } else {
      state.tools.push({
        name: payload.tool_name || "tool",
        status: ok ? "done" : "error",
        output_preview: payload.output_preview || "",
        tool_call_id: toolCallId,
      });
    }
    if (!ok) renderErrorsPanel(currentEngagement);
    scheduleChatRender();
    if (openDrawerJobId === jobId) renderDrawerContent();
    return;
  }
  if (type === "tool_error" && features.streamAgentTools) {
    const toolCallId = payload.tool_call_id || "";
    const row = matchToolRow(state.tools, payload.tool_name, toolCallId);
    if (row) {
      row.status = "error";
      if (payload.error) row.output_preview = String(payload.error);
      if (toolCallId) row.tool_call_id = toolCallId;
    } else {
      state.tools.push({
        name: payload.tool_name || "tool",
        status: "error",
        output_preview: payload.error ? String(payload.error) : "",
        tool_call_id: toolCallId,
      });
    }
    scheduleChatRender();
    if (openDrawerJobId === jobId) renderDrawerContent();
  }
}

function handleStreamEvent(parsed) {
  const isNew = appendDetailEvent(parsed);
  if (isNew && features.streamAgentOutput) {
    handleChatEvent(parsed);
  }
  if (shouldRefreshOnEvent(parsed)) {
    void refreshDetail();
  }
}

function connectEngagementStream(engagementId) {
  disconnectEngagementStream();
  if (!engagementId) return;

  const controller = new AbortController();
  sseAbort = controller;
  sseStatus = "connecting";
  updateStreamBadge();

  let backoff = 1000;

  async function connect() {
    try {
      const response = await fetch(
        `${apiBase()}/v1/engagements/${encodeURIComponent(engagementId)}/stream`,
        {
          headers: { Accept: "text/event-stream", ...authHeaders() },
          cache: "no-store",
          signal: controller.signal,
        },
      );
      if (!response.ok || !response.body) {
        throw new Error(`SSE HTTP ${response.status}`);
      }
      backoff = 1000;
      sseStatus = "open";
      updateStreamBadge();

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";
        for (const part of parts) {
          parseSseChunk(part, (data) => {
            try {
              const parsed = JSON.parse(data);
              handleStreamEvent(parsed);
            } catch {
              // ignore malformed
            }
          });
        }
      }
      throw new Error("stream ended");
    } catch (err) {
      if (controller.signal.aborted) return;
      if (currentDetailId !== engagementId) return;
      sseStatus = "error";
      updateStreamBadge();
      await new Promise((r) => setTimeout(r, backoff));
      backoff = Math.min(backoff * 2, 30000);
      if (!controller.signal.aborted && currentDetailId === engagementId) {
        void connect();
      }
    }
  }

  void connect();
}

function planPersonasLabel(eng) {
  const plan = eng.planner_plan || [];
  if (!plan.length) return "";
  const mode = (eng.execution_mode || "").toLowerCase();
  const sep = mode === "staged" ? " → " : " + ";
  let label = plan.join(sep);
  if (eng.synthesis_persona && plan.length > 1) {
    label += `${mode === "staged" ? " → " : " → "}${eng.synthesis_persona} (synthesis)`;
  }
  return label;
}

function renderFinalReport(eng) {
  const heading = $("#detail-final-report-heading");
  const el = $("#detail-final-report");
  const report = eng.final_report;
  if (!report || typeof report !== "object") {
    heading?.classList.add("hidden");
    el?.classList.add("hidden");
    if (el) el.innerHTML = "";
    return;
  }
  heading?.classList.remove("hidden");
  el?.classList.remove("hidden");
  if (el) {
    el.innerHTML = `<div class="finding-card card finding-final"><div class="finding-body">${formatFindingHtml(report)}</div></div>`;
  }
}

function renderFindings(findings) {
  detailFindings = findings || [];
  const list = $("#detail-findings");
  if (!detailFindings.length) {
    list.innerHTML = '<p class="muted">No findings yet.</p>';
    return;
  }
  list.innerHTML = detailFindings
    .map((item) => {
      const persona = item.persona || item.agent || "—";
      const jobId = item.job_id || "—";
      const html = formatFindingHtml(item.finding || item);
      const viewBtn =
        features.streamAgentOutput && jobId !== "—"
          ? `<button type="button" class="btn-link btn-view-job" data-job="${escapeHtml(jobId)}">View job</button>`
          : "";
      return `
      <div class="finding-card card">
        <strong>${escapeHtml(persona)}</strong>
        <code>${escapeHtml(jobId)}</code> ${viewBtn}
        <div class="finding-body">${html}</div>
      </div>`;
    })
    .join("");
  list.querySelectorAll(".btn-view-job").forEach((btn) => {
    btn.addEventListener("click", () => openJobDetail(btn.dataset.job));
  });
}

function renderPlanner(eng) {
  const el = $("#detail-planner");
  const blocks = [];
  if (eng.planner_status) {
    blocks.push(`<div class="planner-block"><strong>Status:</strong> ${escapeHtml(eng.planner_status)}</div>`);
  }
  if (eng.planner_plan?.length) {
    const mode = (eng.execution_mode || "parallel").toLowerCase();
    blocks.push(
      `<div class="planner-block"><strong>Plan (${escapeHtml(mode)}):</strong> ${escapeHtml(planPersonasLabel(eng))}</div>`,
    );
    if (hasOperatorToken()) {
      blocks.push(
        `<div class="planner-block"><button type="button" class="secondary" id="btn-promote-plan">Save plan to catalog</button></div>`,
      );
    }
  }
  if (eng.synthesis_status && eng.synthesis_status !== "skipped") {
    blocks.push(
      `<div class="planner-block"><strong>Synthesis:</strong> ${escapeHtml(eng.synthesis_persona || "—")} (${escapeHtml(eng.synthesis_status)})</div>`,
    );
  }
  if (eng.planner_rationale) {
    blocks.push(`<div class="planner-block"><strong>Rationale:</strong> ${escapeHtml(eng.planner_rationale)}</div>`);
  }
  if (eng.planner_error) {
    blocks.push(`<div class="planner-block"><strong>Error:</strong> ${escapeHtml(eng.planner_error)}</div>`);
  }
  if (features.streamAgentOutput && currentDetailId) {
    const pj = plannerJobId(currentDetailId);
    blocks.push(
      `<div class="planner-block"><button type="button" class="btn-link btn-view-job" data-job="${escapeHtml(pj)}">View planner run</button></div>`,
    );
  }
  el.innerHTML = blocks.length ? blocks.join("") : "—";
  const status = (eng.planner_status || "").toLowerCase();
  el.classList.toggle("planner-error", status === "error");
  const rationale = (eng.planner_rationale || "").toLowerCase();
  el.classList.toggle("planner-warning", rationale.includes("fallback") && status !== "error");
  el.querySelectorAll(".btn-view-job").forEach((btn) => {
    btn.addEventListener("click", () => openJobDetail(btn.dataset.job));
  });
  const promoteBtn = $("#btn-promote-plan");
  if (promoteBtn) {
    promoteBtn.addEventListener("click", () => void promptPromotePlan(eng));
  }
}

function pendingJobQueueHint(jobs, infra) {
  const pending = jobs.filter((j) => (j.status || "").toLowerCase() === "pending");
  if (!pending.length) return "";
  const now = Date.now();
  const stale = pending.some((j) => {
    if (!j.created_at) return true;
    const created = Date.parse(j.created_at);
    return Number.isNaN(created) || now - created > 30_000;
  });
  if (!stale) return "";
  const depth = infra?.queue?.depth;
  const backend = infra?.queue?.backend || "";
  if (backend === "memory") {
    return "Worker queue is in-memory (split-brain risk) — ensure Redis is up and restart API + workers.";
  }
  if (typeof depth === "number" && depth > 0) {
    return `Worker queue backlog (${depth} jobs) — staged pipeline prioritizes the first persona.`;
  }
  return "No worker consumer detected — start: uv run egregore worker --daemon";
}

async function fetchInfraHealth() {
  try {
    const data = await request("/health/infra");
    infraHealthCache = data;
    return data;
  } catch {
    return infraHealthCache;
  }
}

function showInfraBanner(infra) {
  const el = $("#detail-infra-banner");
  if (!el || !infra?.queue) return;
  if (infra.queue.backend === "memory") {
    el.textContent =
      "Infrastructure warning: job queue backend is memory — workers may not see API enqueued jobs.";
    el.classList.remove("hidden");
    return;
  }
  el.classList.add("hidden");
  el.textContent = "";
}

function personaFromJobId(jobId) {
  if (!jobId) return "—";
  if (jobId.startsWith("planner:")) return "planner";
  if (jobId.startsWith("critic:")) return "critic";
  if (jobId.startsWith("coordinator:")) return "coordinator";
  const dash = jobId.indexOf("-");
  return dash > 0 ? jobId.slice(0, dash) : jobId;
}

function mergeJobRows(jobsFromApi, eng) {
  const byId = new Map();
  for (const job of jobsFromApi) {
    byId.set(job.job_id, { ...job });
  }
  const completed = new Set(eng.completed_personas || []);
  const failed = new Set(eng.failed_personas || []);

  function statusFor(persona, jobId) {
    if (completed.has(persona)) return "completed";
    if (failed.has(persona)) return "failed";
    const existing = byId.get(jobId);
    if (existing?.status) return existing.status;
    return "pending";
  }

  function ensureRow(jobId, persona) {
    if (!jobId || byId.has(jobId)) return;
    byId.set(jobId, {
      job_id: jobId,
      persona: persona || personaFromJobId(jobId),
      status: statusFor(persona || personaFromJobId(jobId), jobId),
    });
  }

  for (const jobId of eng.job_ids || []) {
    ensureRow(jobId, personaFromJobId(jobId));
  }
  for (const item of eng.findings_summary || []) {
    ensureRow(item.job_id, item.persona);
  }

  return [...byId.values()];
}

function renderJobsTable(jobs, eng) {
  let rows = mergeJobRows(jobs, eng);
  if (features.streamAgentOutput && currentDetailId) {
    const pj = plannerJobId(currentDetailId);
    const hasPlanner = rows.some((j) => j.job_id === pj);
    if (!hasPlanner) {
      rows.unshift({
        persona: "planner",
        status: eng.planner_status || "—",
        job_id: pj,
        _pseudo: true,
      });
    }
  }
  $("#detail-jobs").innerHTML = rows
    .map((j) => {
      const persona = j.persona || "—";
      const actionCell = features.streamAgentOutput
        ? `<td><button type="button" class="btn-link btn-view-job" data-job="${escapeHtml(j.job_id)}">View</button></td>`
        : "";
      const memoryCell =
        persona !== "—" && persona !== "planner"
          ? `<td><button type="button" class="btn-link btn-view-memory" data-agent="${escapeHtml(persona)}">Memory</button></td>`
          : "<td class=\"muted\">—</td>";
      return `
      <tr>
        <td>${escapeHtml(persona)}</td>
        <td><span class="badge ${statusBadgeClass(j.status)}">${escapeHtml(formatStatusLabel(j.status))}</span></td>
        <td><code>${escapeHtml(j.job_id)}</code></td>
        ${actionCell}
        ${memoryCell}
      </tr>`;
    })
    .join("");
  $("#detail-jobs").querySelectorAll(".btn-view-job").forEach((btn) => {
    btn.addEventListener("click", () => openJobDetail(btn.dataset.job));
  });
  $("#detail-jobs").querySelectorAll(".btn-view-memory").forEach((btn) => {
    btn.addEventListener("click", () => openMemoryDetail(btn.dataset.agent));
  });
}

function jobEventsFor(jobId) {
  return detailEvents.filter((e) => {
    const payload = eventPayload(e);
    return payload.job_id === jobId;
  });
}

function findingHtmlForJob(jobId) {
  const match = detailFindings.find((f) => f.job_id === jobId);
  return match ? formatFindingHtml(match.finding || match) : null;
}

function findingForJob(jobId) {
  const match = detailFindings.find((f) => f.job_id === jobId);
  return match ? formatFinding(match.finding || match) : null;
}

function renderDrawerTranscript(jobId) {
  const state = chatState.get(jobId);
  const lifecycle = jobEventsFor(jobId).filter((e) => {
    const t = e.type || "";
    return t === "status" || ["job_started", "job_finished"].includes(t) || e.phase;
  });
  const parts = [];
  for (const e of lifecycle) {
    parts.push(`<div class="chat-tool-row">${escapeHtml(egressSummary(e))}</div>`);
  }
  if (state) {
    for (const t of state.tools) {
      const cls = t.status === "done" ? "ok" : t.status === "error" ? "err" : "";
      parts.push(`<div class="chat-tool-row ${cls}">${escapeHtml(t.name)} — ${escapeHtml(t.status)}</div>`);
    }
    const bubbleCls = state.streaming ? "chat-bubble streaming" : "chat-bubble";
    parts.push(`<div class="${bubbleCls}">${transcriptPlaceholder(state, jobId)}</div>`);
  }
  if (!parts.length) {
    return '<p class="muted">No transcript (streaming disabled or job pending).</p>';
  }
  return parts.join("");
}

function memoryCacheKey(engagementId, agent) {
  return `${engagementId}:${agent}`;
}

async function fetchMemoryEntries(agent, { force = false } = {}) {
  if (!currentDetailId || !agent) return [];
  const key = memoryCacheKey(currentDetailId, agent);
  if (!force && memoryCache.has(key)) return memoryCache.get(key);
  const data = await getEngagementMemory(currentDetailId, { agent, limit: 50 });
  const entries = data.entries || [];
  memoryCache.set(key, entries);
  return entries;
}

function formatMemoryTimestamp(value) {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return String(value);
  }
}

function memoryFetchErrorHtml(err) {
  if (err instanceof ApiError && err.status === 404) {
    return (
      '<p class="alert err">Memory API not found — restart the API server ' +
      "(<code>uv run egregore serve --port 8080</code>) to load the latest code.</p>"
    );
  }
  return `<p class="alert err">${escapeHtml(err.message || String(err))}</p>`;
}

function renderMemoryTimeline(entries, { agent } = {}) {
  if (!entries.length) {
    const job = detailJobs.find((j) => j.persona === agent);
    const failed = (job?.status || "").toLowerCase() === "failed";
    const extra = failed
      ? "<p class=\"muted\">Job failed — episodic memory is recorded when the worker publishes a finding. Check Live events or Langfuse.</p>"
      : "";
    return `<p class="muted">No memory entries for this agent in this engagement.</p>${extra}`;
  }
  return entries
    .map((entry) => {
      const typeCls = entry.memory_type === "pending_finding" ? "warn" : "";
      const body = formatFindingHtml(entry.content_parsed || entry);
      const jobLink = entry.source_job_id
        ? `<button type="button" class="btn-link btn-memory-job" data-job="${escapeHtml(entry.source_job_id)}">${escapeHtml(entry.source_job_id)}</button>`
        : "—";
      return `
      <div class="memory-entry card">
        <div class="memory-entry-meta">
          <span class="badge ${typeCls}">${escapeHtml(entry.memory_type || "memory")}</span>
          <span class="muted">${escapeHtml(formatMemoryTimestamp(entry.created_at))}</span>
          <span class="muted">trust ${(entry.trust_score ?? 0).toFixed(2)}</span>
        </div>
        <p class="muted">Job: ${jobLink}</p>
        <div class="finding-body">${body}</div>
      </div>`;
    })
    .join("");
}

async function renderDrawerMemory(persona) {
  const el = $("#drawer-tab-memory");
  if (!el || !currentDetailId || !persona) {
    if (el) el.innerHTML = '<p class="muted">No agent selected.</p>';
    return;
  }
  el.innerHTML = '<p class="muted">Loading memory…</p>';
  try {
    const entries = await fetchMemoryEntries(persona);
    el.innerHTML = renderMemoryTimeline(entries, { agent: persona });
    el.querySelectorAll(".btn-memory-job").forEach((btn) => {
      btn.addEventListener("click", () => openJobDetail(btn.dataset.job));
    });
  } catch (err) {
    el.innerHTML = memoryFetchErrorHtml(err);
  }
}

async function openMemoryDetail(agent) {
  if (!currentDetailId || !agent) return;
  openMemoryAgent = agent;
  $("#memory-drawer-agent").textContent = agent;
  $("#memory-drawer-engagement").textContent = currentDetailId;
  $("#memory-drawer-body").innerHTML = '<p class="muted">Loading memory…</p>';
  $("#memory-drawer-backdrop").classList.remove("hidden");
  $("#memory-detail-drawer").classList.remove("hidden");
  try {
    const entries = await fetchMemoryEntries(agent, { force: true });
    const el = $("#memory-drawer-body");
    el.innerHTML = renderMemoryTimeline(entries, { agent });
    el.querySelectorAll(".btn-memory-job").forEach((btn) => {
      btn.addEventListener("click", () => {
        closeMemoryDetail();
        openJobDetail(btn.dataset.job);
      });
    });
  } catch (err) {
    $("#memory-drawer-body").innerHTML = memoryFetchErrorHtml(err);
  }
}

function closeMemoryDetail() {
  openMemoryAgent = null;
  $("#memory-drawer-backdrop").classList.add("hidden");
  $("#memory-detail-drawer").classList.add("hidden");
}

function catalogHeaders(kind) {
  if (kind === "agents") return ["Name", "Role", "Enabled", "Trust"];
  if (kind === "tools") return ["ID", "Description", "Risk", "Enabled"];
  if (kind === "skills") return ["ID", "Description", "Enabled"];
  return ["ID", "Description", "Enabled"];
}

function renderCatalogTable() {
  const thead = $("#catalog-thead");
  const tbody = $("#catalog-body");
  const headers = catalogHeaders(catalogKind);
  thead.innerHTML = `<tr>${headers.map((h) => `<th>${escapeHtml(h)}</th>`).join("")}</tr>`;

  if (!catalogRows.length) {
    tbody.innerHTML = `<tr><td colspan="${headers.length}" class="muted">No items.</td></tr>`;
    return;
  }

  if (catalogKind === "agents") {
    tbody.innerHTML = catalogRows
      .map((agent) => {
        const name = agent.name || "—";
        return `
        <tr class="catalog-row" data-agent-name="${escapeHtml(name)}">
          <td><strong>${escapeHtml(name)}</strong></td>
          <td>${escapeHtml(agent.role || "—")}</td>
          <td>${agent.enabled === false ? "no" : "yes"}</td>
          <td>${typeof agent.empirical_trust === "number" ? agent.empirical_trust.toFixed(2) : "—"}</td>
        </tr>`;
      })
      .join("");
    tbody.querySelectorAll(".catalog-row").forEach((row) => {
      row.addEventListener("click", () => void showCatalogAgentDetail(row.dataset.agentName));
    });
    return;
  }

  if (catalogKind === "tools") {
    tbody.innerHTML = catalogRows
      .map((tool) => {
        const id = tool.tool_id || tool.id || tool.name || "—";
        return `
        <tr>
          <td><code>${escapeHtml(id)}</code></td>
          <td>${escapeHtml(tool.description || "—")}</td>
          <td>${escapeHtml(tool.risk_tier || "—")}</td>
          <td>${tool.enabled === false ? "no" : "yes"}</td>
        </tr>`;
      })
      .join("");
    return;
  }

  if (catalogKind === "skills") {
    tbody.innerHTML = catalogRows
      .map((skill) => {
        const id = skill.skill_id || skill.id || "—";
        return `
        <tr class="catalog-row" data-skill-id="${escapeHtml(id)}">
          <td><code>${escapeHtml(id)}</code></td>
          <td>${escapeHtml(skill.description || "—")}</td>
          <td>${skill.enabled === false ? "no" : "yes"}</td>
        </tr>`;
      })
      .join("");
    tbody.querySelectorAll(".catalog-row").forEach((row) => {
      row.addEventListener("click", () => void showCatalogSkillDetail(row.dataset.skillId));
    });
    return;
  }

  tbody.innerHTML = catalogRows
    .map((plan) => {
      const id = plan.plan_id || plan.id || "—";
      return `
      <tr>
        <td><code>${escapeHtml(id)}</code></td>
        <td>${escapeHtml(plan.description || plan.name || "—")}</td>
        <td>${plan.enabled === false ? "no" : "yes"}</td>
      </tr>`;
    })
    .join("");
}

async function showCatalogAgentDetail(name) {
  const detailEl = $("#catalog-detail");
  if (!name) {
    detailEl.classList.add("hidden");
    return;
  }
  detailEl.classList.remove("hidden");
  detailEl.innerHTML = '<p class="muted">Loading agent detail…</p>';
  try {
    const [agent, skillsData] = await Promise.all([getCatalogAgent(name), listCatalogSkills()]);
    catalogSelectedAgent = agent;
    const allSkills = (skillsData.skills || []).map((s) => s.skill_id || s.id).filter(Boolean);
    const selected = new Set(agent.skills || []);
    const editable = hasOperatorToken();
    const skillsHtml = allSkills.length
      ? `<div class="catalog-skill-chips">${allSkills
          .map((sid) => {
            const checked = selected.has(sid) ? "checked" : "";
            const disabled = editable ? "" : "disabled";
            return `<label class="catalog-chip"><input type="checkbox" data-skill="${escapeHtml(sid)}" ${checked} ${disabled} /> ${escapeHtml(sid)}</label>`;
          })
          .join("")}</div>`
      : '<p class="muted">No skills in catalog.</p>';
    const banner = editable
      ? ""
      : '<p class="alert warn">Read-only — set operator Token in header to edit.</p>';
    const actions = editable
      ? `<div class="row" style="margin-top: 0.75rem">
          <button type="button" id="btn-agent-save">Save</button>
          <button type="button" class="secondary" id="btn-agent-reload">Save &amp; reload workers</button>
        </div>
        <div id="catalog-agent-msg" class="muted" style="margin-top: 0.5rem"></div>`
      : "";
    detailEl.innerHTML = `
      <div class="catalog-editor">
        ${banner}
        <h3 style="margin: 0 0 0.5rem">${escapeHtml(agent.name)}</h3>
        <p class="muted">${escapeHtml(agent.description || "—")}</p>
        <p><strong>Role:</strong> ${escapeHtml(agent.role || "—")}</p>
        <p><strong>Trust:</strong> ${typeof agent.empirical_trust === "number" ? agent.empirical_trust.toFixed(2) : "—"}</p>
        <label class="catalog-editor-label">System prompt
          <textarea id="catalog-agent-prompt" rows="12" ${editable ? "" : "readonly"}>${escapeHtml(agent.system_prompt || "")}</textarea>
        </label>
        <p style="margin: 0.75rem 0 0.35rem"><strong>Skills</strong></p>
        ${skillsHtml}
        ${actions}
      </div>`;
    if (editable) {
      const save = async (reload) => {
        const msg = $("#catalog-agent-msg");
        msg.textContent = "Saving…";
        const skills = [...detailEl.querySelectorAll('input[data-skill]:checked')].map((el) => el.dataset.skill);
        try {
          await putCatalogAgent(name, {
            description: agent.description || "",
            role: agent.role || "worker",
            output_schema: agent.output_schema,
            tools: agent.tools || [],
            skills,
            system_prompt: $("#catalog-agent-prompt").value,
            enabled: agent.enabled !== false,
            profile_id: agent.profile_id || "",
          });
          if (reload) await reloadCatalog();
          msg.textContent = reload ? "Saved and catalog reloaded." : "Saved.";
          void refreshCatalog();
        } catch (err) {
          msg.textContent = "";
          msg.innerHTML = `<span class="err">${escapeHtml(err.message || String(err))}</span>`;
        }
      };
      $("#btn-agent-save").addEventListener("click", () => void save(false));
      $("#btn-agent-reload").addEventListener("click", () => void save(true));
    }
  } catch (err) {
    detailEl.innerHTML = `<p class="alert err">${escapeHtml(err.message || String(err))}</p>`;
  }
}

async function showCatalogSkillDetail(skillId) {
  const detailEl = $("#catalog-detail");
  if (!skillId) {
    detailEl.classList.add("hidden");
    return;
  }
  detailEl.classList.remove("hidden");
  detailEl.innerHTML = '<p class="muted">Loading skill detail…</p>';
  try {
    const skill = await getCatalogSkill(skillId);
    catalogSelectedSkill = skill;
    const editable = hasOperatorToken();
    const id = skill.skill_id || skill.id || skillId;
    const staging = skill.staging_status || "";
    const banner = editable
      ? ""
      : '<p class="alert warn">Read-only — set operator Token in header to edit.</p>';
    const approveBtn =
      editable && staging === "draft"
        ? '<button type="button" class="secondary" id="btn-skill-approve">Approve</button>'
        : "";
    const actions = editable
      ? `<div class="row" style="margin-top: 0.75rem">
          <button type="button" id="btn-skill-save">Save</button>
          ${approveBtn}
        </div>
        <div id="catalog-skill-msg" class="muted" style="margin-top: 0.5rem"></div>`
      : "";
    detailEl.innerHTML = `
      <div class="catalog-editor">
        ${banner}
        <h3 style="margin: 0 0 0.5rem"><code>${escapeHtml(id)}</code></h3>
        <p class="muted">Status: ${escapeHtml(staging || "—")} · v${skill.version ?? 1}</p>
        <label class="catalog-editor-label">Description
          <input type="text" id="catalog-skill-desc" class="wide" value="${escapeHtml(skill.description || "")}" ${editable ? "" : "readonly"} />
        </label>
        <label class="catalog-editor-label">Body (SKILL.md)
          <textarea id="catalog-skill-body" rows="16" ${editable ? "" : "readonly"}>${escapeHtml(skill.body || "")}</textarea>
        </label>
        ${actions}
      </div>`;
    if (editable) {
      const msg = $("#catalog-skill-msg");
      $("#btn-skill-save").addEventListener("click", async () => {
        msg.textContent = "Saving…";
        try {
          await putCatalogSkill(id, {
            name: skill.name || id,
            description: $("#catalog-skill-desc").value,
            body: $("#catalog-skill-body").value,
            profile_id: skill.profile_id || "",
            trust_tier: skill.trust_tier || "community",
            staging_status: staging || "draft",
          });
          msg.textContent = "Saved.";
          void refreshCatalog();
        } catch (err) {
          msg.textContent = "";
          msg.innerHTML = `<span class="err">${escapeHtml(err.message || String(err))}</span>`;
        }
      });
      const approveEl = $("#btn-skill-approve");
      if (approveEl) {
        approveEl.addEventListener("click", async () => {
          msg.textContent = "Approving…";
          try {
            await approveCatalogSkill(id);
            msg.textContent = "Approved.";
            void showCatalogSkillDetail(id);
            void refreshCatalog();
          } catch (err) {
            msg.textContent = "";
            msg.innerHTML = `<span class="err">${escapeHtml(err.message || String(err))}</span>`;
          }
        });
      }
    }
  } catch (err) {
    detailEl.innerHTML = `<p class="alert err">${escapeHtml(err.message || String(err))}</p>`;
  }
}

async function promptPromotePlan(eng) {
  const plan = eng.planner_plan || [];
  if (!plan.length) {
    alert("No planner plan to promote.");
    return;
  }
  const defaultId = `eng-${(eng.engagement_id || "plan").slice(-8)}`;
  const planId = prompt(
    `Plan ID for catalog (personas: ${plan.join(" → ")}):`,
    defaultId,
  );
  if (!planId || !planId.trim()) return;
  const activate = confirm("Activate this plan for the profile after save?");
  try {
    const saved = await promoteEngagementPlan(eng.engagement_id, {
      plan_id: planId.trim(),
      activate,
    });
    alert(`Plan saved: ${saved.id || planId}\nOpen Catalog → Plans to review.`);
    setTab("catalog");
    setCatalogKind("plans");
  } catch (err) {
    alert(`Promote failed: ${err.message || err}`);
  }
}

function renderGlobalMemoryTable(entries) {
  if (!entries.length) {
    return '<p class="muted">No memory entries for this tenant.</p>';
  }
  const rows = entries
    .map((entry) => {
      const engId = entry.investigation_id || "—";
      const engLink =
        engId !== "—"
          ? `<button type="button" class="btn-link btn-memory-engagement" data-engagement="${escapeHtml(engId)}">${escapeHtml(engId)}</button>`
          : "—";
      const body = formatFindingHtml(entry.content_parsed || entry);
      return `
      <tr>
        <td class="muted">${escapeHtml(formatMemoryTimestamp(entry.created_at))}</td>
        <td><strong>${escapeHtml(entry.source_agent || "—")}</strong></td>
        <td>${engLink}</td>
        <td><span class="badge">${escapeHtml(entry.memory_type || "memory")}</span></td>
        <td class="memory-feed-body"><div class="finding-body">${body}</div></td>
      </tr>`;
    })
    .join("");
  return `
    <table class="memory-feed-table">
      <thead>
        <tr>
          <th>Time</th>
          <th>Agent</th>
          <th>Engagement</th>
          <th>Type</th>
          <th>Content</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
}

async function refreshMemoryFeed() {
  const loading = $("#memory-loading");
  const errEl = $("#memory-error");
  const body = $("#memory-feed-body");
  if (!loading || !body) return;
  loading.classList.remove("hidden");
  showError(errEl, null);
  try {
    const agent = $("#memory-agent-filter")?.value || "";
    const data = await listTenantMemory({ agent: agent || undefined, limit: 100 });
    const entries = data.entries || [];
    body.innerHTML = renderGlobalMemoryTable(entries);
    body.querySelectorAll(".btn-memory-engagement").forEach((btn) => {
      btn.addEventListener("click", () => {
        openDetail(btn.dataset.engagement);
        setTab("engagements");
      });
    });
  } catch (err) {
    body.innerHTML = "";
    showError(errEl, err.message || String(err));
  } finally {
    loading.classList.add("hidden");
  }
}

async function refreshCatalog() {
  const loading = $("#catalog-loading");
  const errEl = $("#catalog-error");
  loading.classList.remove("hidden");
  showError(errEl, null);
  $("#catalog-detail").classList.add("hidden");
  catalogSelectedAgent = null;
  catalogSelectedSkill = null;
  try {
    let data;
    if (catalogKind === "agents") {
      data = await listCatalogAgents();
      catalogRows = data.agents || [];
    } else if (catalogKind === "tools") {
      data = await listCatalogTools();
      catalogRows = data.tools || [];
    } else if (catalogKind === "skills") {
      data = await listCatalogSkills();
      catalogRows = data.skills || [];
    } else {
      data = await listCatalogPlans();
      catalogRows = data.plans || [];
    }
    renderCatalogTable();
  } catch (err) {
    catalogRows = [];
    renderCatalogTable();
    showError(errEl, err.message || String(err));
  } finally {
    loading.classList.add("hidden");
  }
}

function setCatalogKind(kind) {
  catalogKind = kind;
  document.querySelectorAll(".catalog-subtabs button").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.catalogKind === kind);
  });
  void refreshCatalog();
}

function renderDrawerContent() {
  if (!openDrawerJobId) return;
  const jobId = openDrawerJobId;
  const state = chatState.get(jobId);
  const job = detailJobs.find((j) => j.job_id === jobId);
  const persona = state?.persona || job?.persona || (jobId.startsWith("planner:") ? "planner" : "—");
  const status = job?.status || (state?.streaming ? "running" : "—");
  $("#drawer-job-id").textContent = jobId;
  $("#drawer-job-meta").textContent = `${persona} · ${formatStatusLabel(status)}`;
  $("#drawer-tab-transcript").innerHTML = renderDrawerTranscript(jobId);
  const findingHtml = findingHtmlForJob(jobId);
  const findingEl = $("#drawer-tab-finding");
  findingEl.innerHTML = findingHtml
    ? `<div class="finding-body">${findingHtml}</div>`
    : '<p class="muted">No finding for this job yet.</p>';
  findingEl.classList.toggle("hidden", drawerTab !== "finding");
  $("#drawer-tab-transcript").classList.toggle("hidden", drawerTab !== "transcript");
  const memoryEl = $("#drawer-tab-memory");
  memoryEl.classList.toggle("hidden", drawerTab !== "memory");
  if (drawerTab === "memory") {
    void renderDrawerMemory(persona);
  }
}

function openJobDetail(jobId) {
  if (!jobId) return;
  openDrawerJobId = jobId;
  drawerTab = features.streamAgentOutput ? "transcript" : "finding";
  document.querySelectorAll(".job-drawer-tabs button").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.drawerTab === drawerTab);
  });
  $("#job-drawer-backdrop").classList.remove("hidden");
  $("#job-detail-drawer").classList.remove("hidden");
  renderDrawerContent();
}

function closeJobDetail() {
  openDrawerJobId = null;
  $("#job-drawer-backdrop").classList.add("hidden");
  $("#job-detail-drawer").classList.add("hidden");
}

async function refreshEngagements() {
  const loading = $("#engagements-loading");
  const errEl = $("#engagements-error");
  const body = $("#engagements-body");
  loading.classList.remove("hidden");
  showError(errEl, null);
  try {
    const data = await listEngagements();
    const rows = data.engagements || [];
    body.innerHTML = rows
      .map(
        (eng) => `
      <tr class="clickable" data-id="${escapeHtml(eng.engagement_id)}">
        <td><code>${escapeHtml(eng.engagement_id.slice(0, 8))}…</code></td>
        <td><span class="badge ${statusBadgeClass(eng.status)}">${escapeHtml(formatStatusLabel(eng.status))}</span></td>
        <td>${escapeHtml(eng.goal || "—")}</td>
        <td>${escapeHtml((eng.completed_personas || []).join(", ") || "—")}</td>
      </tr>`,
      )
      .join("");
    body.querySelectorAll("tr.clickable").forEach((tr) => {
      tr.addEventListener("click", () => openDetail(tr.dataset.id));
    });
  } catch (err) {
    showError(errEl, err.message || String(err));
  } finally {
    loading.classList.add("hidden");
  }
}

async function refreshApprovals() {
  const errEl = $("#approvals-error");
  const list = $("#approvals-list");
  const empty = $("#approvals-empty");
  const countEl = $("#approval-count");
  showError(errEl, null);
  try {
    const data = await listPendingApprovals();
    const approvals = data.approvals || [];
    countEl.textContent = approvals.length ? `(${approvals.length})` : "";
    empty.classList.toggle("hidden", approvals.length > 0);
    list.innerHTML = approvals
      .map(
        (a) => `
      <div class="approval-card card" data-job="${escapeHtml(a.job_id)}" data-approval="${escapeHtml(a.approval_id)}">
        <strong>${escapeHtml(a.persona)}</strong> — <code>${escapeHtml(a.tool_name)}</code>
        <span class="badge">${escapeHtml(a.risk_level)}</span>
        <pre>${escapeHtml(JSON.stringify(a.tool_args, null, 2))}</pre>
        <div class="row" style="margin-top: 0.5rem">
          <button type="button" class="ok btn-approve">Approve</button>
          <button type="button" class="danger btn-reject">Reject</button>
        </div>
        <div class="approval-msg muted"></div>
      </div>`,
      )
      .join("");

    list.querySelectorAll(".btn-approve").forEach((btn) => {
      btn.addEventListener("click", () => decideApproval(btn, "approve"));
    });
    list.querySelectorAll(".btn-reject").forEach((btn) => {
      btn.addEventListener("click", () => decideApproval(btn, "reject"));
    });
  } catch (err) {
    showError(errEl, err.message || String(err));
  }
}

async function decideApproval(btn, decision) {
  const card = btn.closest(".approval-card");
  const jobId = card.dataset.job;
  const approvalId = card.dataset.approval;
  const msg = card.querySelector(".approval-msg");
  btn.disabled = true;
  msg.textContent = "…";
  try {
    await resumeJob(jobId, {
      decision,
      approval_id: approvalId,
      actor: "minimal-console",
    });
    msg.textContent = decision === "approve" ? "Approved" : "Rejected";
    card.style.opacity = "0.5";
    setTimeout(() => void refreshApprovals(), 800);
  } catch (err) {
    msg.textContent = err.message || String(err);
    btn.disabled = false;
  }
}

function openDetail(id) {
  currentDetailId = id;
  detailEvents = [];
  seenEventKeys.clear();
  chatState.clear();
  memoryCache.clear();
  openDrawerJobId = null;
  closeJobDetail();
  closeMemoryDetail();
  $("#detail-id").textContent = id;
  $("#detail-panel").classList.remove("hidden");
  $("#detail-events").textContent = "Waiting for engagement stream…";
  $("#detail-response").innerHTML = '<span class="muted">Waiting for agent stream…</span>';
  $("#btn-langfuse").href = langfuseEngagementUrl(id);
  location.hash = `detail/${id}`;
  void hydrateDetailEvents(id);
  void fetchInfraHealth().then(showInfraBanner);
  connectEngagementStream(id);
  void refreshDetail();
}

async function hydrateDetailEvents(engagementId) {
  try {
    const events = await getEngagementEvents(engagementId);
    if (!Array.isArray(events) || !events.length) return;
    for (const event of events.slice(-200)) {
      if (appendDetailEvent(event) && features.streamAgentOutput) {
        handleChatEvent(event);
      }
    }
  } catch {
    // SSE may still deliver events; keep placeholder until then
  }
}

function closeDetail() {
  currentDetailId = null;
  disconnectEngagementStream();
  chatState.clear();
  memoryCache.clear();
  closeJobDetail();
  closeMemoryDetail();
  $("#detail-panel").classList.add("hidden");
  if (location.hash.startsWith("#detail/")) {
    history.replaceState(null, "", location.pathname);
  }
}

async function refreshDetail() {
  if (!currentDetailId) return;
  const errEl = $("#detail-error");
  showError(errEl, null);
  try {
    const [eng, jobsData, infra] = await Promise.all([
      getEngagement(currentDetailId),
      getInvestigationJobs(currentDetailId),
      fetchInfraHealth(),
    ]);
    currentEngagement = eng;
    const jobs = jobsData.jobs || [];
    detailJobs = jobs;
    const { displayStatus, completedPersonas } = deriveEngagementView(eng, jobs);
    $("#detail-status").textContent = formatStatusLabel(displayStatus);
    $("#detail-status").className = `badge ${statusBadgeClass(displayStatus)}`;
    const phaseEl = $("#detail-phase");
    if (phaseEl) {
      phaseEl.textContent = eng.latest_phase ? `Last event: ${eng.latest_phase}` : "";
      phaseEl.classList.toggle("hidden", !eng.latest_phase);
    }
    $("#detail-goal").textContent = eng.goal ? `Goal: ${eng.goal}` : "";
    currentEngagementGoal = eng.goal || "";
    $("#detail-personas").textContent = `Completed: ${completedPersonas.join(", ") || "—"}`;
    const running = ["enqueued", "running", "planning"].includes((displayStatus || "").toLowerCase());
    detailPollMs = running ? 3000 : 15000;
    renderPlanner(eng);
    renderFinalReport(eng);
    renderFindings(eng.findings_summary || []);
    renderJobsTable(jobs, eng);
    hydrateTranscriptFromDetail(eng, jobs);
    renderErrorsPanel(eng);
    renderResponseThread();
    if (openDrawerJobId) renderDrawerContent();
    const jobsHint = $("#detail-jobs-hint");
    if (jobsHint) {
      const hint = pendingJobQueueHint(jobs, infra);
      jobsHint.textContent = hint;
      jobsHint.classList.toggle("hidden", !hint);
    }
    showInfraBanner(infra);
  } catch (err) {
    showError(errEl, err.message || String(err));
  }
}

function persistConfig() {
  const api = normalizeApiBase($("#api-base").value.trim());
  $("#api-base").value = api;
  localStorage.setItem(STORAGE_API, api);
  localStorage.setItem(STORAGE_TOKEN, $("#api-token").value);
  localStorage.setItem(STORAGE_LANGFUSE, $("#langfuse-host").value);
  if (currentDetailId) {
    $("#btn-langfuse").href = langfuseEngagementUrl(currentDetailId);
    connectEngagementStream(currentDetailId);
  }
  void loadFeatures();
}

function resolveGatewayUrl(port) {
  const host = window.location.hostname || "127.0.0.1";
  const proto = window.location.protocol === "http:" ? "http" : "https";
  return `${proto}://${host}:${port}`;
}

function normalizeApiBase(url) {
  if (!url) return url;
  return url.replace(/:30990(\/|$)/, ":30880$1");
}

function migrateApiBase(stored, fallback) {
  if (!stored) return fallback;
  try {
    const u = new URL(stored);
    const here = window.location;
    if (here.port === "30300" && u.port === "30880") {
      return here.origin;
    }
  } catch (_) {
    /* ignore */
  }
  return stored;
}

function resolveApiBase() {
  const here = window.location;
  // TLS gateway serves API on the same port as ui-minimal — never call :30880 from browser.
  if (here.port === "30300") {
    return here.origin;
  }
  const defaults = window.EGREGORE_DEFAULTS || {};
  const stored = migrateApiBase(
    normalizeApiBase(localStorage.getItem(STORAGE_API)),
    defaults.api || resolveGatewayUrl(30880),
  );
  return stored || defaults.api || resolveGatewayUrl(30880);
}

function loadConfig() {
  const defaults = window.EGREGORE_DEFAULTS || {};
  const fallbackLangfuse = defaults.langfuse || resolveGatewayUrl(30001);
  const api = resolveApiBase();
  $("#api-base").value = api;
  localStorage.setItem(STORAGE_API, api);
  $("#api-token").value = localStorage.getItem(STORAGE_TOKEN) || "";
  $("#langfuse-host").value =
    localStorage.getItem(STORAGE_LANGFUSE) || defaults.langfuse || fallbackLangfuse;
}

function parseHash() {
  const m = location.hash.match(/^#detail\/(.+)$/);
  if (m) {
    openDetail(decodeURIComponent(m[1]));
  }
}

document.querySelectorAll("nav.tabs button").forEach((btn) => {
  btn.addEventListener("click", () => {
    setTab(btn.dataset.tab);
    if (btn.dataset.tab === "engagements") void refreshEngagements();
    if (btn.dataset.tab === "catalog") void refreshCatalog();
    if (btn.dataset.tab === "memory") void refreshMemoryFeed();
    if (btn.dataset.tab === "approvals") void refreshApprovals();
  });
});

$("#form-new").addEventListener("submit", async (e) => {
  e.preventDefault();
  const goal = $("#goal-input").value.trim();
  if (!goal) return;
  const errEl = $("#new-error");
  const btn = $("#btn-start");
  showError(errEl, null);
  btn.disabled = true;
  btn.textContent = "Starting…";
  try {
    const response = await createEngagement(goal);
    const engagementId = response.engagement_id;
    $("#goal-input").value = "";
    openDetail(engagementId);
    setTab("engagements");
    void refreshEngagements();
  } catch (err) {
    showError(errEl, err.message || String(err));
  } finally {
    btn.disabled = false;
    btn.textContent = "Start";
  }
});

$("#btn-refresh-list").addEventListener("click", () => void refreshEngagements());
$("#btn-refresh-approvals").addEventListener("click", () => void refreshApprovals());
$("#btn-detail-refresh").addEventListener("click", () => void refreshDetail());
$("#btn-detail-close").addEventListener("click", closeDetail);
$("#btn-drawer-close").addEventListener("click", closeJobDetail);
$("#job-drawer-backdrop").addEventListener("click", closeJobDetail);
$("#btn-memory-drawer-close").addEventListener("click", closeMemoryDetail);
$("#memory-drawer-backdrop").addEventListener("click", closeMemoryDetail);
$("#btn-refresh-catalog").addEventListener("click", () => void refreshCatalog());
const memoryRefreshBtn = $("#btn-refresh-memory");
if (memoryRefreshBtn) memoryRefreshBtn.addEventListener("click", () => void refreshMemoryFeed());
const memoryFilterEl = $("#memory-agent-filter");
if (memoryFilterEl) memoryFilterEl.addEventListener("change", () => void refreshMemoryFeed());

document.querySelectorAll(".catalog-subtabs button").forEach((btn) => {
  btn.addEventListener("click", () => setCatalogKind(btn.dataset.catalogKind || "agents"));
});

document.querySelectorAll(".job-drawer-tabs button").forEach((btn) => {
  btn.addEventListener("click", () => {
    drawerTab = btn.dataset.drawerTab || "transcript";
    document.querySelectorAll(".job-drawer-tabs button").forEach((b) => {
      b.classList.toggle("active", b.dataset.drawerTab === drawerTab);
    });
    renderDrawerContent();
  });
});

$("#btn-health").addEventListener("click", async () => {
  try {
    const [snap, health] = await Promise.all([
      getStatus().catch(() => null),
      fetch(`${apiBase()}/health`).then((r) => (r.ok ? r.json() : null)).catch(() => null),
    ]);
    const stream = health?.features?.stream_agent_output ? "on" : "off";
    const extra = snap
      ? `events: ${snap.events_count}, findings: ${snap.findings_count}, awaiting: ${(snap.awaiting_approval || []).length}`
      : "status endpoint unavailable";
    alert(`OK — stream: ${stream}, ${extra}`);
  } catch (err) {
    alert(`Health check failed: ${err.message || err}`);
  }
});

$("#api-base").addEventListener("change", persistConfig);
$("#api-token").addEventListener("change", persistConfig);
$("#langfuse-host").addEventListener("change", persistConfig);

loadConfig();
void loadFeatures().then(() => {
  parseHash();
});

let lastDetailPoll = 0;
setInterval(() => {
  if (document.querySelector('[data-tab="approvals"].active')) {
    void refreshApprovals();
  }
  if (!currentDetailId) return;
  const now = Date.now();
  if (now - lastDetailPoll >= detailPollMs) {
    lastDetailPoll = now;
    void refreshDetail();
  }
}, 1000);
