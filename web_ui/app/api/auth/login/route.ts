import crypto from "node:crypto"

import { cookies } from "next/headers"
import { NextResponse } from "next/server"

import { PKCE_COOKIE_NAME, cookieOptions, encodeCookieJson, fetchOidcMetadata } from "@/lib/auth/server-session"

export const runtime = "nodejs"

function base64Url(input: Buffer): string {
  return input.toString("base64url")
}

export async function GET(request: Request) {
  const issuer = process.env.NEXT_PUBLIC_OIDC_ISSUER?.replace(/\/$/, "")
  const clientId = process.env.OIDC_CLIENT_ID
  if (!issuer || !clientId) {
    return NextResponse.json({ code: "OIDC_NOT_CONFIGURED" }, { status: 503 })
  }

  const url = new URL(request.url)
  const redirectUri = process.env.OIDC_REDIRECT_URI || `${url.origin}/api/auth/callback`
  const verifier = base64Url(crypto.randomBytes(32))
  const challenge = base64Url(crypto.createHash("sha256").update(verifier).digest())
  const state = base64Url(crypto.randomBytes(24))
  const metadata = await fetchOidcMetadata(issuer)
  const authUrl = new URL(metadata.authorization_endpoint)
  authUrl.searchParams.set("client_id", clientId)
  authUrl.searchParams.set("redirect_uri", redirectUri)
  authUrl.searchParams.set("response_type", "code")
  authUrl.searchParams.set("scope", "openid profile email")
  authUrl.searchParams.set("code_challenge", challenge)
  authUrl.searchParams.set("code_challenge_method", "S256")
  authUrl.searchParams.set("state", state)

  const cookieStore = await cookies()
  cookieStore.set(
    PKCE_COOKIE_NAME,
    encodeCookieJson({ verifier, state, redirectUri }),
    cookieOptions(600),
  )
  return NextResponse.redirect(authUrl)
}
