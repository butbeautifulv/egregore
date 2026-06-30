"use client"

import type { ReactNode } from "react"
import { MotionFadeIn } from "@/vendor/gui/motion/motion-fade-in"
import { cn } from "@/vendor/gui/utils"

export function DataTableShell({
  toolbar,
  children,
  className,
}: {
  toolbar?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <MotionFadeIn className={cn("flex min-w-0 flex-col gap-3", className)}>
      {toolbar && <div className="min-h-10 min-w-0">{toolbar}</div>}
      <div className="min-w-0 overflow-x-auto rounded-md border">{children}</div>
    </MotionFadeIn>
  )
}
