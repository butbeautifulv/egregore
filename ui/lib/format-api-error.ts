import { ApiError } from "@/lib/api-client"

type ApiErrorDetail = {
  detail?: string | { message?: string; code?: string }
}

function parseApiErrorDetail(exc: ApiError): ApiErrorDetail["detail"] | null {
  try {
    const parsed = JSON.parse(exc.message) as ApiErrorDetail
    return parsed.detail ?? null
  } catch {
    return null
  }
}

/** Strip HTML error pages and normalize proxy/upstream bodies. */
export function normalizeApiErrorBody(text: string, status?: number): string {
  const trimmed = text.trim()
  if (!trimmed) {
    return statusTitle(status) ?? "Request failed"
  }
  if (/^<!DOCTYPE/i.test(trimmed) || /^<html/i.test(trimmed)) {
    return statusTitle(status) ?? "API returned an HTML error page"
  }
  if (trimmed.length > 400) {
    return `${trimmed.slice(0, 400)}…`
  }
  return trimmed
}

function statusTitle(status?: number): string | null {
  if (status === undefined) return null
  if (status === 404) return "Not found"
  if (status === 408) return "Request timed out"
  if (status === 429) return "Too many requests"
  if (status >= 500) return "API unavailable"
  if (status >= 400) return "Request failed"
  return null
}

export function getApiErrorCode(exc: unknown): string | null {
  if (!(exc instanceof ApiError)) {
    return null
  }
  const detail = parseApiErrorDetail(exc)
  if (detail && typeof detail === "object" && typeof detail.code === "string") {
    return detail.code
  }
  return null
}

export function formatApiError(exc: unknown, fallback: string): string {
  if (!(exc instanceof ApiError)) {
    return exc instanceof Error ? normalizeApiErrorBody(exc.message) || fallback : fallback
  }
  const detail = parseApiErrorDetail(exc)
  if (typeof detail === "string") {
    return normalizeApiErrorBody(detail, exc.status)
  }
  if (detail && typeof detail === "object" && typeof detail.message === "string") {
    return normalizeApiErrorBody(detail.message, exc.status)
  }
  const normalized = normalizeApiErrorBody(exc.message, exc.status)
  if (normalized && normalized !== exc.message) {
    return normalized
  }
  if (/^internal server error$/i.test(exc.message.trim())) {
    return statusTitle(exc.status) ?? fallback
  }
  return normalized || fallback
}

export function getApiErrorTitle(exc: unknown, context?: string): string {
  if (isLlmUnavailableError(exc)) {
    return "LLM unavailable"
  }
  if (isPersistenceUnavailableError(exc)) {
    return "Persistence unavailable"
  }
  if (exc instanceof ApiError) {
    if (exc.status === 404) return "Not found"
    if (exc.status === 408) return "Request timed out"
    if (exc.status === 429) return "Too many requests"
    if (exc.status >= 500) return "API unavailable"
  }
  const code = getApiErrorCode(exc)
  if (code === "unknown_resource" || code === "validation_error") {
    return "Configuration error"
  }
  if (context === "planner") {
    return "Planner failed"
  }
  return context ? `${context} failed` : "Request failed"
}

export function isRetryableApiError(exc: unknown): boolean {
  if (isLlmUnavailableError(exc) || isPersistenceUnavailableError(exc)) {
    return true
  }
  if (exc instanceof ApiError) {
    return exc.status >= 500 || exc.status === 408 || exc.status === 429
  }
  return true
}

export function formatPlannerError(raw: string | null | undefined): string {
  if (!raw?.trim()) {
    return "Planner could not build a persona plan."
  }
  const text = raw.trim()
  if (/unparseable planner response/i.test(text) || /empty personas/i.test(text)) {
    return "Planner could not build a persona plan. Try rephrasing the goal or start a new work order."
  }
  if (/personas not in catalog/i.test(text)) {
    return "Planner selected personas that are not in the catalog. Reload the catalog or start a new work order."
  }
  return normalizeApiErrorBody(text)
}

export function isLlmUnavailableError(exc: unknown): boolean {
  return getApiErrorCode(exc) === "llm_unavailable"
}

export function isPersistenceUnavailableError(exc: unknown): boolean {
  return getApiErrorCode(exc) === "persistence_unavailable"
}

export function isRetryableSessionError(exc: unknown): boolean {
  const code = getApiErrorCode(exc)
  return code === "llm_unavailable" || code === "persistence_unavailable"
}

export function sessionErrorTitle(exc: unknown): string {
  if (isLlmUnavailableError(exc)) {
    return "LLM unavailable"
  }
  if (isPersistenceUnavailableError(exc)) {
    return "Persistence unavailable"
  }
  const code = getApiErrorCode(exc)
  if (code === "unknown_resource" || code === "validation_error") {
    return "Session configuration error"
  }
  return "Session error"
}
