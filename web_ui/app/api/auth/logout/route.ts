import { cookies } from "next/headers"
import { NextResponse } from "next/server"

import { PKCE_COOKIE_NAME, SESSION_COOKIE_NAME } from "@/lib/auth/server-session"

export const runtime = "nodejs"

async function clearAuthCookies() {
  const cookieStore = await cookies()
  cookieStore.delete(SESSION_COOKIE_NAME)
  cookieStore.delete(PKCE_COOKIE_NAME)
}

export async function POST() {
  await clearAuthCookies()
  return NextResponse.json({ ok: true })
}

export async function GET(request: Request) {
  await clearAuthCookies()
  return NextResponse.redirect(new URL("/login", request.url))
}
