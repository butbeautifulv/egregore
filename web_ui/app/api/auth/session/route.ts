import { NextResponse } from "next/server"

import { getServerSession } from "@/lib/auth/server-session"

export const runtime = "nodejs"

export async function GET() {
  const session = await getServerSession()
  if (!session) {
    return NextResponse.json({ authenticated: false })
  }
  return NextResponse.json({
    authenticated: true,
    sub: session.sub,
    email: session.email,
    organization_id: session.organization_id,
    roles: session.roles ?? [],
  })
}
