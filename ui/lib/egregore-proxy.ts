const DEFAULT_UPSTREAM = "http://egregore-api:8080"

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
])

export function upstreamBase(): string {
  return process.env.EGREGORE_API_UPSTREAM ?? DEFAULT_UPSTREAM
}

function buildUpstreamUrl(pathSegments: string[], search: string): string {
  const path = pathSegments.map(encodeURIComponent).join("/")
  const base = upstreamBase().replace(/\/$/, "")
  return `${base}/${path}${search}`
}

function forwardRequestHeaders(request: Request): Headers {
  const headers = new Headers()
  for (const [key, value] of request.headers.entries()) {
    if (HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
      continue
    }
    headers.set(key, value)
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

  const upstream = await fetch(targetUrl, {
    method,
    headers: forwardRequestHeaders(request),
    body: hasBody ? await request.arrayBuffer() : undefined,
    cache: "no-store",
    duplex: hasBody ? "half" : undefined,
  } as RequestInit)

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: forwardResponseHeaders(upstream),
  })
}
