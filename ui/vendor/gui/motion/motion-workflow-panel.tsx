"use client"

import { AnimatePresence, motion, useReducedMotion } from "motion/react"
import type { ReactNode } from "react"
import type { ItemWorkflowPhase } from "@/vendor/gui/motion/types"
import {
  workflowFade,
  workflowScaleIn,
  workflowSlideUp,
} from "@/vendor/gui/motion/motion-workflow-presets"
import { cn } from "@/vendor/gui/utils"

const phasePresets = {
  not_started: workflowSlideUp,
  in_progress_form: workflowSlideUp,
  pending_review: workflowFade,
  rejected: workflowSlideUp,
  completed: workflowScaleIn,
} as const

export function MotionWorkflowPanel({
  phase,
  children,
  className,
}: {
  phase: ItemWorkflowPhase
  children: ReactNode
  className?: string
}) {
  const reduceMotion = useReducedMotion()
  const preset = phasePresets[phase]

  if (reduceMotion) {
    return <div className={className}>{children}</div>
  }

  return (
    <AnimatePresence initial={false}>
      <motion.div
        key={phase}
        className={cn(className)}
        initial={preset.initial}
        animate={preset.animate}
        exit={preset.exit ?? workflowFade.exit}
        transition={preset.transition}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  )
}
