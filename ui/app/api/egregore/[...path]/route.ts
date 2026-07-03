import { proxyToEgregoreApi } from "@/lib/egregore-proxy"

export const dynamic = "force-dynamic"
export const runtime = "nodejs"

type RouteContext = {
  params: Promise<{ path: string[] }>
}

async function handle(request: Request, context: RouteContext) {
  const { path } = await context.params
  return proxyToEgregoreApi(request, path)
}

export const GET = handle
export const POST = handle
export const PUT = handle
export const PATCH = handle
export const DELETE = handle
export const HEAD = handle
export const OPTIONS = handle
