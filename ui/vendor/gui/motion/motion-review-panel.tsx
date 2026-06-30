"use client"

import { AnimatePresence, motion, useReducedMotion } from "motion/react"
import type { ReactNode } from "react"
import { reviewSlideUp } from "@/vendor/gui/motion/motion-workflow-presets"
import { cn } from "@/vendor/gui/utils"

export function MotionReviewPanel({
  open,
  children,
  className,
}: {
  open: boolean
  children: ReactNode
  className?: string
}) {
  const reduceMotion = useReducedMotion()

  if (reduceMotion) {
    return open ? <div className={className}>{children}</div> : null
  }

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className={cn(className)}
          initial={reviewSlideUp.initial}
          animate={reviewSlideUp.animate}
          exit={reviewSlideUp.exit}
          transition={reviewSlideUp.transition}
        >
          {children}
        </motion.div>
      ) : null}
    </AnimatePresence>
  )
}
