"use client"

import type { ReactNode } from "react"

import { CHAT_COLUMN_CLASS } from "@/lib/chat-layout"
import { useSidebar } from "@/vendor/gui/ui/sidebar"
import { cn } from "@/vendor/gui/utils"

export function FollowUpComposerDock({ children }: { children: ReactNode }) {
  const { state, isMobile } = useSidebar()

  const leftClass = isMobile
    ? "left-0"
    : state === "collapsed"
      ? "left-[var(--sidebar-width-icon)]"
      : "left-[var(--sidebar-width)]"

  return (
    <div
      className={cn(
        "fixed bottom-0 right-0 z-30 border-t bg-background/95 px-4 py-4 backdrop-blur supports-[backdrop-filter]:bg-background/80",
        leftClass,
      )}
    >
      <div className={CHAT_COLUMN_CLASS}>{children}</div>
    </div>
  )
}
