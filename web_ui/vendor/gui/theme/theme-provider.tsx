"use client"

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react"
import { flushSync } from "react-dom"
import { ThemeHotkey } from "@/vendor/gui/theme/theme-hotkey"
import { THEME_STORAGE_KEY } from "@/vendor/gui/theme/blocking-script"

type Theme = "light" | "dark" | "system"
type ResolvedTheme = "light" | "dark"

type ThemeContextValue = {
  theme: Theme
  resolvedTheme: ResolvedTheme
  setTheme: (theme: Theme) => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

function subscribeSystemTheme(onStoreChange: () => void) {
  if (typeof window === "undefined") return () => {}

  const media = window.matchMedia("(prefers-color-scheme: dark)")
  media.addEventListener("change", onStoreChange)
  return () => media.removeEventListener("change", onStoreChange)
}

function getStoredTheme(): Theme {
  return (localStorage.getItem(THEME_STORAGE_KEY) as Theme | null) ?? "system"
}

function getSystemResolvedTheme(): ResolvedTheme {
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light"
}

function resolveTheme(theme: Theme): ResolvedTheme {
  if (theme === "system") return getSystemResolvedTheme()
  return theme
}

function withoutTransitions(apply: () => ResolvedTheme): ResolvedTheme {
  if (typeof document === "undefined") {
    return apply()
  }

  const style = document.createElement("style")
  style.appendChild(
    document.createTextNode(
      "*,*::before,*::after{-webkit-transition:none!important;-moz-transition:none!important;-o-transition:none!important;-ms-transition:none!important;transition:none!important}",
    ),
  )
  document.head.appendChild(style)

  const resolved = apply()
  void window.getComputedStyle(document.body).opacity

  window.setTimeout(() => {
    document.head.removeChild(style)
  }, 1)

  return resolved
}

function applyThemeToDocument(theme: Theme, options?: { disableTransitions?: boolean }) {
  const apply = () => {
    const resolved = resolveTheme(theme)
    const root = document.documentElement
    root.classList.toggle("dark", resolved === "dark")
    root.style.colorScheme = resolved
    return resolved
  }

  if (options?.disableTransitions) {
    return withoutTransitions(apply)
  }

  return apply()
}

function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>("system")
  const [hydrated, setHydrated] = useState(false)

  const systemResolvedTheme = useSyncExternalStore(
    subscribeSystemTheme,
    getSystemResolvedTheme,
    () => "light" as ResolvedTheme,
  )

  const resolvedTheme: ResolvedTheme =
    theme === "system" ? systemResolvedTheme : theme

  useLayoutEffect(() => {
    // Must run synchronously before paint to avoid a theme flash — the
    // blocking <script> in <head> already set the DOM class, this just
    // brings React's state in sync with it on mount.
    const stored = getStoredTheme()
    // eslint-disable-next-line react-hooks/set-state-in-effect -- pre-paint sync from localStorage, not derivable at render time
    setThemeState(stored)
    applyThemeToDocument(stored)
    setHydrated(true)
  }, [])

  useLayoutEffect(() => {
    if (!hydrated) return
    applyThemeToDocument(theme)
  }, [theme, systemResolvedTheme, hydrated])

  useEffect(() => {
    function onStorage(event: StorageEvent) {
      if (event.key !== THEME_STORAGE_KEY) return
      const next = (event.newValue as Theme | null) ?? "system"
      flushSync(() => setThemeState(next))
      applyThemeToDocument(next, { disableTransitions: true })
    }

    window.addEventListener("storage", onStorage)
    return () => window.removeEventListener("storage", onStorage)
  }, [])

  const setTheme = useCallback((next: Theme) => {
    localStorage.setItem(THEME_STORAGE_KEY, next)
    applyThemeToDocument(next, { disableTransitions: true })
    flushSync(() => setThemeState(next))
  }, [])

  const value = useMemo(
    () => ({ theme, resolvedTheme, setTheme }),
    [theme, resolvedTheme, setTheme],
  )

  return (
    <ThemeContext.Provider value={value}>
      <ThemeHotkey />
      {children}
    </ThemeContext.Provider>
  )
}

function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) {
    throw new Error("useTheme must be used within ThemeProvider")
  }
  return ctx
}

export { ThemeProvider, useTheme }
