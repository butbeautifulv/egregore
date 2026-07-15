import { cookies } from "next/headers"

export const SESSION_COOKIE_NAME = "egregore_session"
export const PKCE_COOKIE_NAME = "egregore_pkce"

export type OidcSession = {
  access_token: string
  sub?: string
  email?: string
  organization_id?: string
  roles?: string[]
  exp?: number
}

export type PkceState = {
  verifier: string
  state: string
  redirectUri: string
}

export function cookieOptions(maxAge: number) {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge,
  }
}

export function encodeCookieJson(value: unknown): string {
  return Buffer.from(JSON.stringify(value), "utf8").toString("base64url")
}

export function decodeCookieJson<T>(value: string | undefined): T | null {
  if (!value) {
    return null
  }
  try {
    return JSON.parse(Buffer.from(value, "base64url").toString("utf8")) as T
  } catch {
    return null
  }
}

export function decodeJwtClaims(token: string): Record<string, unknown> {
  const [, payload] = token.split(".")
  if (!payload) {
    return {}
  }
  return decodeCookieJson<Record<string, unknown>>(payload) ?? {}
}

function stringClaim(claims: Record<string, unknown>, keys: string[]): string {
  for (const key of keys) {
    const value = claims[key]
    if (typeof value === "string" && value.trim()) {
      return value.trim()
    }
  }
  return ""
}

function roleClaims(claims: Record<string, unknown>, clientId: string): string[] {
  const roles = new Set<string>()
  const realmAccess = claims.realm_access
  if (realmAccess && typeof realmAccess === "object" && "roles" in realmAccess) {
    const realmRoles = (realmAccess as { roles?: unknown }).roles
    if (Array.isArray(realmRoles)) {
      for (const role of realmRoles) {
        if (typeof role === "string") roles.add(role)
      }
    }
  }
  const resourceAccess = claims.resource_access
  const clientAccess =
    resourceAccess && typeof resourceAccess === "object"
      ? (resourceAccess as Record<string, { roles?: unknown }>)[clientId]
      : undefined
  if (Array.isArray(clientAccess?.roles)) {
    for (const role of clientAccess.roles) {
      if (typeof role === "string") roles.add(role)
    }
  }
  return [...roles]
}

export function sessionFromAccessToken(accessToken: string, clientId: string): OidcSession {
  const claims = decodeJwtClaims(accessToken)
  const exp = typeof claims.exp === "number" ? claims.exp : undefined
  return {
    access_token: accessToken,
    sub: stringClaim(claims, ["sub"]),
    email: stringClaim(claims, ["email", "preferred_username"]),
    organization_id: stringClaim(claims, ["organization_id", "org_id", "org", "tenant_id"]),
    roles: roleClaims(claims, clientId),
    exp,
  }
}

export async function getServerSession(): Promise<OidcSession | null> {
  const cookieStore = await cookies()
  const session = decodeCookieJson<OidcSession>(cookieStore.get(SESSION_COOKIE_NAME)?.value)
  if (!session?.access_token) {
    return null
  }
  if (session.exp && session.exp <= Math.floor(Date.now() / 1000)) {
    return null
  }
  return session
}

export async function fetchOidcMetadata(issuer: string) {
  const normalized = issuer.replace(/\/$/, "")
  const fallback = {
    authorization_endpoint: `${normalized}/protocol/openid-connect/auth`,
    token_endpoint: `${normalized}/protocol/openid-connect/token`,
  }
  try {
    const response = await fetch(`${normalized}/.well-known/openid-configuration`, { cache: "no-store" })
    if (!response.ok) {
      return fallback
    }
    const metadata = (await response.json()) as Partial<typeof fallback>
    return {
      authorization_endpoint: metadata.authorization_endpoint ?? fallback.authorization_endpoint,
      token_endpoint: metadata.token_endpoint ?? fallback.token_endpoint,
    }
  } catch {
    return fallback
  }
}
