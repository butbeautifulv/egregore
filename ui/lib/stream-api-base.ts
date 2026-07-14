/** Browser-direct SSE base URL (nginx gateway same-origin in prod; API upstream in dev). */

export function streamApiBase(): string {
  const raw = process.env.NEXT_PUBLIC_STREAM_API_BASE
  if (raw !== undefined) {
    return raw.replace(/\/$/, "")
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
