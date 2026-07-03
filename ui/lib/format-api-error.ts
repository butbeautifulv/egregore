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
    return exc instanceof Error ? exc.message : fallback
  }
  const detail = parseApiErrorDetail(exc)
  if (typeof detail === "string") {
    return detail
  }
  if (detail && typeof detail === "object" && typeof detail.message === "string") {
    return detail.message
  }
  return exc.message || fallback
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
