export const SESSION_COOKIE_NAME = "egregore_session"
export const SESSION_STORAGE_KEY = "egregore_session"

export type ClientSession = {
  authenticated: boolean
  sub?: string
  email?: string
  organization_id?: string
  roles?: string[]
}

function allowLocalTokenFallback(): boolean {
  return process.env.NEXT_PUBLIC_ALLOW_LOCAL_TOKEN === "1"
}

export async function getClientSession(): Promise<ClientSession> {
  if (typeof window === "undefined") {
    return { authenticated: false }
  }
  const response = await fetch("/api/auth/session", {
    credentials: "include",
    cache: "no-store",
  })
  if (!response.ok) {
    return { authenticated: false }
  }
  return response.json() as Promise<ClientSession>
}

export function getClientSessionToken(): string | null {
  if (typeof window === "undefined") {
    return null
  }
  if (!allowLocalTokenFallback()) {
    return null
  }

  const fromStorage = window.localStorage.getItem(SESSION_STORAGE_KEY)
  if (fromStorage) {
    return fromStorage
  }
  return null
}

export function setClientSessionToken(token: string) {
  if (typeof window === "undefined" || !allowLocalTokenFallback()) {
    return
  }
  window.localStorage.setItem(SESSION_STORAGE_KEY, token)
}

export function clearClientSessionToken() {
  if (typeof window === "undefined") {
    return
  }
  window.localStorage.removeItem(SESSION_STORAGE_KEY)
}
