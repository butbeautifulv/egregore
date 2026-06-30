"use client"

import { motion, useReducedMotion } from "motion/react"
import type { ReactNode } from "react"
import { workflowPulse } from "@/vendor/gui/motion/motion-workflow-presets"
import { cn } from "@/vendor/gui/utils"

export function MotionPulseText({
  children,
  className,
  active = true,
}: {
  children: ReactNode
  className?: string
  active?: boolean
}) {
  const reduceMotion = useReducedMotion()

  if (reduceMotion || !active) {
    return <div className={className}>{children}</div>
  }

  return (
    <motion.div
      className={cn(className)}
      animate={workflowPulse.animate}
      transition={workflowPulse.transition}
    >
      {children}
    </motion.div>
  )
}
