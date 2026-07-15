import * as React from "react"

const COMPACT_SHELL_BREAKPOINT = 1024

function subscribe(callback: () => void) {
  const mql = window.matchMedia(`(max-width: ${COMPACT_SHELL_BREAKPOINT - 1}px)`)
  mql.addEventListener("change", callback)
  return () => mql.removeEventListener("change", callback)
}

function getSnapshot() {
  return window.innerWidth < COMPACT_SHELL_BREAKPOINT
}

function getServerSnapshot() {
  return false
}

export function useIsCompactShell() {
  return React.useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)
}
