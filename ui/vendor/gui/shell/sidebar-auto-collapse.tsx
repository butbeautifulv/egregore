"use client"

import { useEffect, useRef } from "react"
import { useSidebar } from "@/vendor/gui/ui/sidebar"
import { useIsCompactShell } from "@/vendor/gui/hooks/use-compact-shell"

const MANUAL_EXPAND_KEY = "sidebar_manual_expand"

export function SidebarAutoCollapse() {
  const isCompact = useIsCompactShell()
  const { isMobile, open, setOpen } = useSidebar()
  const prevOpen = useRef(open)
  const prevCompact = useRef(isCompact)

  useEffect(() => {
    if (isMobile) return

    if (!prevOpen.current && open) {
      sessionStorage.setItem(MANUAL_EXPAND_KEY, "1")
    }

    if (prevOpen.current && !open) {
      sessionStorage.removeItem(MANUAL_EXPAND_KEY)
    }

    prevOpen.current = open
  }, [open, isMobile])

  useEffect(() => {
    if (isMobile) return

    if (isCompact) {
      const manual = sessionStorage.getItem(MANUAL_EXPAND_KEY) === "1"
      if (!manual && open) {
        setOpen(false)
      }
    } else if (prevCompact.current) {
      sessionStorage.removeItem(MANUAL_EXPAND_KEY)
    }

    prevCompact.current = isCompact
  }, [isCompact, isMobile, open, setOpen])

  return null
}
