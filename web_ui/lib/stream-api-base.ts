import { PROXY_BASE } from "@/lib/api-upstream"

/**
 * SSE base URL.
 * Browser: same-origin `/api/egregore` proxy (matches REST; avoids CORS on auth/workspace headers).
 * SSR/dev server: direct API upstream.
 */
export function streamApiBase(): string {
  const raw = process.env.NEXT_PUBLIC_STREAM_API_BASE
  if (raw !== undefined) {
    return raw.replace(/\/$/, "")
  }
  if (typeof window !== "undefined") {
    return PROXY_BASE
  }
  if (process.env.NODE_ENV === "development") {
    return "http://127.0.0.1:8080"
  }
  return ""
}

export function buildStreamUrl(path: string): string {
  const base = streamApiBase()
  const normalized = path.startsWith("/") ? path : `/${path}`
  return base ? `${base}${normalized}` : normalized
}
