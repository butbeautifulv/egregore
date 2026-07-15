"use client"

import { motion, useReducedMotion } from "motion/react"
import type { ReactNode } from "react"
import { fadeIn, fadeInUp, staggerContainer, staggerItem } from "@/vendor/gui/motion/motion-presets"
import {
  workflowStaggerContainer,
  workflowStaggerItem,
} from "@/vendor/gui/motion/motion-workflow-presets"
import { cn } from "@/vendor/gui/utils"

export function MotionFadeIn({
  children,
  className,
  delay = 0,
  variant = "up",
}: {
  children: ReactNode
  className?: string
  delay?: number
  variant?: "up" | "fade"
}) {
  const reduceMotion = useReducedMotion()
  const preset = variant === "fade" ? fadeIn : fadeInUp

  if (reduceMotion) {
    return <div className={className}>{children}</div>
  }

  return (
    <motion.div
      className={className}
      initial={preset.initial}
      animate={preset.animate}
      transition={{ ...preset.transition, delay }}
    >
      {children}
    </motion.div>
  )
}

export function MotionPageEnter({
  children,
  className,
  pageKey,
}: {
  children: ReactNode
  className?: string
  pageKey: string
}) {
  const reduceMotion = useReducedMotion()

  if (reduceMotion) {
    return <div className={className}>{children}</div>
  }

  return (
    <motion.div
      key={pageKey}
      className={className}
      initial={fadeInUp.initial}
      animate={fadeInUp.animate}
      transition={fadeInUp.transition}
    >
      {children}
    </motion.div>
  )
}

export function MotionStagger({
  children,
  className,
  variant = "default",
}: {
  children: ReactNode
  className?: string
  variant?: "default" | "workflow"
}) {
  const reduceMotion = useReducedMotion()
  const container = variant === "workflow" ? workflowStaggerContainer : staggerContainer

  if (reduceMotion) {
    return <div className={className}>{children}</div>
  }

  return (
    <motion.div
      className={className}
      initial="initial"
      animate="animate"
      variants={container}
    >
      {children}
    </motion.div>
  )
}

export function MotionStaggerItem({
  children,
  className,
  variant = "default",
}: {
  children: ReactNode
  className?: string
  variant?: "default" | "workflow"
}) {
  const reduceMotion = useReducedMotion()
  const item = variant === "workflow" ? workflowStaggerItem : staggerItem

  if (reduceMotion) {
    return <div className={className}>{children}</div>
  }

  return (
    <motion.div className={cn(className)} variants={item}>
      {children}
    </motion.div>
  )
}
