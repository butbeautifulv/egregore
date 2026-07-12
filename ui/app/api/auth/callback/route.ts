import { cookies } from "next/headers"
import { NextResponse } from "next/server"

import {
  PKCE_COOKIE_NAME,
  SESSION_COOKIE_NAME,
  cookieOptions,
  decodeCookieJson,
  encodeCookieJson,
  fetchOidcMetadata,
  sessionFromAccessToken,
  type PkceState,
} from "@/lib/auth/server-session"

export const runtime = "nodejs"

export async function GET(request: Request) {
  const issuer = process.env.NEXT_PUBLIC_OIDC_ISSUER?.replace(/\/$/, "")
  const clientId = process.env.OIDC_CLIENT_ID
  if (!issuer || !clientId) {
    return NextResponse.json({ code: "OIDC_NOT_CONFIGURED" }, { status: 503 })
  }

  const url = new URL(request.url)
  const code = url.searchParams.get("code")
  const state = url.searchParams.get("state")
  if (!code || !state) {
    return NextResponse.json({ code: "OIDC_CALLBACK_INVALID" }, { status: 400 })
  }

  const cookieStore = await cookies()
  const pkce = decodeCookieJson<PkceState>(cookieStore.get(PKCE_COOKIE_NAME)?.value)
  if (!pkce || pkce.state !== state) {
    return NextResponse.json({ code: "OIDC_STATE_MISMATCH" }, { status: 400 })
  }

  const metadata = await fetchOidcMetadata(issuer)
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: clientId,
    redirect_uri: pkce.redirectUri,
    code,
    code_verifier: pkce.verifier,
  })
  if (process.env.OIDC_CLIENT_SECRET) {
    body.set("client_secret", process.env.OIDC_CLIENT_SECRET)
  }

  const tokenResponse = await fetch(metadata.token_endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
    cache: "no-store",
  })
  if (!tokenResponse.ok) {
    return NextResponse.json({ code: "OIDC_TOKEN_EXCHANGE_FAILED" }, { status: 502 })
  }
  const tokenSet = (await tokenResponse.json()) as { access_token?: string; expires_in?: number }
  if (!tokenSet.access_token) {
    return NextResponse.json({ code: "OIDC_ACCESS_TOKEN_MISSING" }, { status: 502 })
  }

  const session = sessionFromAccessToken(tokenSet.access_token, clientId)
  const maxAge = tokenSet.expires_in ?? (session.exp ? session.exp - Math.floor(Date.now() / 1000) : 3600)
  cookieStore.set(SESSION_COOKIE_NAME, encodeCookieJson(session), cookieOptions(Math.max(60, maxAge)))
  cookieStore.delete(PKCE_COOKIE_NAME)
  return NextResponse.redirect(new URL("/", request.url))
}
