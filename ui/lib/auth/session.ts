export const SESSION_COOKIE_NAME = "egregore_session"
export const SESSION_STORAGE_KEY = "egregore_session"

export function getClientSessionToken(): string | null {
  if (typeof window === "undefined") {
    return null
  }

  const fromStorage = window.localStorage.getItem(SESSION_STORAGE_KEY)
  if (fromStorage) {
    return fromStorage
  }

  const match = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${SESSION_COOKIE_NAME}=`))

  if (!match) {
    return null
  }

  return decodeURIComponent(match.slice(SESSION_COOKIE_NAME.length + 1)) || null
}

export function setClientSessionToken(token: string) {
  if (typeof window === "undefined") {
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
