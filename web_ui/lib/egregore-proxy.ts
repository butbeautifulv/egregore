import { DEFAULT_API_UPSTREAM, WORKSPACE_HEADER } from "@/lib/api-upstream"

const DEFAULT_UPSTREAM = DEFAULT_API_UPSTREAM
const DEFAULT_PROXY_TIMEOUT_MS = 25_000

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
  "host",
  "content-length",
  "cookie",
])

export function upstreamBase(): string {
  return process.env.EGREGORE_API_UPSTREAM ?? DEFAULT_UPSTREAM
}

function proxyTimeoutMs(): number {
  const raw = process.env.EGREGORE_API_PROXY_TIMEOUT_MS
  if (!raw) {
    return DEFAULT_PROXY_TIMEOUT_MS
  }
  const parsed = Number.parseInt(raw, 10)
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return DEFAULT_PROXY_TIMEOUT_MS
  }
  return parsed
}

function isEventStreamRequest(request: Request): boolean {
  const accept = request.headers.get("accept") ?? ""
  return accept.includes("text/event-stream")
}

function buildUpstreamUrl(pathSegments: string[], search: string): string {
  const path = pathSegments.map(encodeURIComponent).join("/")
  const base = upstreamBase().replace(/\/$/, "")
  return `${base}/${path}${search}`
}

function forwardRequestHeaders(request: Request, accessToken?: string): Headers {
  const headers = new Headers()
  for (const [key, value] of request.headers.entries()) {
    if (HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
      continue
    }
    headers.set(key, value)
  }
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`)
  }
  const workspaceId = request.headers.get(WORKSPACE_HEADER)
  if (workspaceId) {
    headers.set(WORKSPACE_HEADER, workspaceId)
  }
  return headers
}

function forwardResponseHeaders(upstream: Response): Headers {
  const headers = new Headers()
  for (const [key, value] of upstream.headers.entries()) {
    if (HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
      continue
    }
    headers.set(key, value)
  }
  const contentType = upstream.headers.get("content-type") ?? ""
  if (contentType.includes("text/event-stream")) {
    headers.set("Cache-Control", "no-cache")
    headers.set("Connection", "keep-alive")
    headers.set("X-Accel-Buffering", "no")
  }
  return headers
}

export async function proxyToEgregoreApi(request: Request, pathSegments: string[]): Promise<Response> {
  const url = new URL(request.url)
  const targetUrl = buildUpstreamUrl(pathSegments, url.search)
  const method = request.method.toUpperCase()
  const hasBody = method !== "GET" && method !== "HEAD"
  const streamRequest = isEventStreamRequest(request)

  const { getServerSession } = await import("@/lib/auth/server-session")
  const session = await getServerSession()

  let upstream: Response
  try {
    upstream = await fetch(targetUrl, {
      method,
      headers: forwardRequestHeaders(request, session?.access_token),
      body: hasBody ? await request.arrayBuffer() : undefined,
      cache: "no-store",
      duplex: hasBody ? "half" : undefined,
      signal: streamRequest ? undefined : AbortSignal.timeout(proxyTimeoutMs()),
    } as RequestInit)
  } catch (exc) {
    if (exc instanceof DOMException && (exc.name === "TimeoutError" || exc.name === "AbortError")) {
      return new Response("Upstream API request timed out", { status: 504 })
    }
    throw exc
  }

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: forwardResponseHeaders(upstream),
  })
}
