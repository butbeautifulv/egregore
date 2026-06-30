export const WORKFLOW_DURATION = 0.28
export const WORKFLOW_SPRING = {
  type: "spring" as const,
  stiffness: 260,
  damping: 32,
}

export const workflowSlideUp = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0 },
  transition: { duration: WORKFLOW_DURATION, ease: "easeOut" as const },
} as const

export const workflowScaleIn = {
  initial: { opacity: 0, scale: 0.98 },
  animate: { opacity: 1, scale: 1 },
  exit: { opacity: 0 },
  transition: WORKFLOW_SPRING,
} as const

export const workflowFade = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 },
  transition: { duration: 0.22, ease: "easeOut" as const },
} as const

/** Kept for exports; rejected now uses slideUp — no shake. */
export const workflowShake = workflowSlideUp

export const workflowPulse = {
  animate: {
    opacity: [1, 0.9, 1] as number[],
  },
  transition: {
    duration: 3.5,
    repeat: Infinity,
    ease: "easeInOut" as const,
  },
} as const

export const badgePop = {
  initial: { opacity: 0, scale: 0.96 },
  animate: { opacity: 1, scale: 1 },
  transition: { type: "spring" as const, stiffness: 320, damping: 28 },
} as const

export const successPulse = {
  animate: { scale: [1, 1.025, 1] as number[] },
  transition: { duration: 0.28, ease: "easeOut" as const },
} as const

export const reviewSlideUp = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0 },
  transition: { duration: 0.24, ease: "easeOut" as const },
} as const

export const WORKFLOW_STAGGER_DELAY = 0.025

export const workflowStaggerContainer = {
  initial: {},
  animate: {
    transition: {
      staggerChildren: WORKFLOW_STAGGER_DELAY,
    },
  },
} as const

export const workflowStaggerItem = {
  initial: { opacity: 0, y: 4 },
  animate: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.22, ease: "easeOut" as const },
  },
} as const
