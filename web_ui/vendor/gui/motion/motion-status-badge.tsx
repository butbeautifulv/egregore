"use client"

import { motion, useReducedMotion } from "motion/react"
import type { ReactNode } from "react"
import { badgePop } from "@/vendor/gui/motion/motion-workflow-presets"
import { cn } from "@/vendor/gui/utils"

export function MotionStatusBadge({
  statusKey,
  children,
  className,
  pulse = false,
}: {
  statusKey: string
  children: ReactNode
  className?: string
  pulse?: boolean
}) {
  const reduceMotion = useReducedMotion()

  if (reduceMotion) {
    return <span className={className}>{children}</span>
  }

  return (
    <motion.span
      key={statusKey}
      className={cn("inline-flex", className)}
      initial={badgePop.initial}
      animate={
        pulse
          ? { ...badgePop.animate, scale: [1, 1.03, 1] as number[] }
          : badgePop.animate
      }
      transition={
        pulse
          ? { scale: { duration: 0.28, ease: "easeOut" }, ...badgePop.transition }
          : badgePop.transition
      }
    >
      {children}
    </motion.span>
  )
}
