"use client"

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useSyncExternalStore,
  type ReactNode,
} from "react"
import { useServerInsertedHTML } from "next/navigation"
import { ThemeHotkey } from "@/vendor/gui/theme/theme-hotkey"
import {
  THEME_BLOCKING_SCRIPT,
  THEME_STORAGE_KEY,
} from "@/vendor/gui/theme/blocking-script"

type Theme = "light" | "dark" | "system"
type ResolvedTheme = "light" | "dark"

type ThemeContextValue = {
  theme: Theme
  resolvedTheme: ResolvedTheme
  setTheme: (theme: Theme) => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

const themeListeners = new Set<() => void>()

function subscribeTheme(onStoreChange: () => void) {
  themeListeners.add(onStoreChange)
  return () => {
    themeListeners.delete(onStoreChange)
  }
}

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

function notifyThemeListeners() {
  themeListeners.forEach((listener) => listener())
}

function resolveTheme(theme: Theme): ResolvedTheme {
  if (theme === "system") return getSystemResolvedTheme()
  return theme
}

function applyThemeToDocument(theme: Theme) {
  const resolved = resolveTheme(theme)
  const root = document.documentElement
  root.classList.toggle("dark", resolved === "dark")
  root.style.colorScheme = resolved
  return resolved
}

function ThemeProvider({ children }: { children: ReactNode }) {
  const inserted = useRef(false)

  useServerInsertedHTML(() => {
    if (inserted.current) return null
    inserted.current = true
    return (
      <script
        dangerouslySetInnerHTML={{ __html: THEME_BLOCKING_SCRIPT }}
        suppressHydrationWarning
      />
    )
  })

  const theme = useSyncExternalStore(
    subscribeTheme,
    getStoredTheme,
    () => "system" as Theme
  )

  const systemResolvedTheme = useSyncExternalStore(
    subscribeSystemTheme,
    getSystemResolvedTheme,
    () => "light" as ResolvedTheme
  )

  const resolvedTheme: ResolvedTheme =
    theme === "system" ? systemResolvedTheme : theme

  useEffect(() => {
    applyThemeToDocument(theme)
  }, [theme, resolvedTheme])

  const setTheme = useCallback((next: Theme) => {
    localStorage.setItem(THEME_STORAGE_KEY, next)
    notifyThemeListeners()
    applyThemeToDocument(next)
  }, [])

  const value = useMemo(
    () => ({ theme, resolvedTheme, setTheme }),
    [theme, resolvedTheme, setTheme]
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
