import { NextResponse } from "next/server"

import { SESSION_COOKIE_NAME } from "@/lib/auth/session"

export async function POST(request: Request) {
  await request.json().catch(() => ({}))
  const token = process.env.EGREGORE_DEMO_TOKEN ?? "egregore-demo-token"
  const response = NextResponse.json({ ok: true, token })
  response.cookies.set(SESSION_COOKIE_NAME, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 7,
  })
  return response
}
