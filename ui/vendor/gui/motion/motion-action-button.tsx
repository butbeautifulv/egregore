"use client"

import { motion, useReducedMotion } from "motion/react"
import type { ReactNode } from "react"
import { pressable } from "@/vendor/gui/motion/motion-presets"
import { successPulse } from "@/vendor/gui/motion/motion-workflow-presets"
import { cn } from "@/vendor/gui/utils"

export function MotionActionButton({
  children,
  className,
  successPulseKey = 0,
}: {
  children: ReactNode
  className?: string
  /** Increment after a successful async action to play a brief scale pulse. */
  successPulseKey?: number
}) {
  const reduceMotion = useReducedMotion()

  if (reduceMotion) {
    return <span className={cn("inline-flex", className)}>{children}</span>
  }

  return (
    <motion.span
      key={successPulseKey > 0 ? `pulse-${successPulseKey}` : "idle"}
      className={cn("inline-flex", className)}
      {...pressable}
      animate={successPulseKey > 0 ? successPulse.animate : undefined}
      transition={successPulseKey > 0 ? successPulse.transition : pressable.transition}
    >
      {children}
    </motion.span>
  )
}
