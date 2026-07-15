export const MOTION_DURATION = 0.2
export const MOTION_EASE = "easeOut" as const
export const STAGGER_DELAY = 0.04

export const fadeInUp = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: MOTION_DURATION, ease: MOTION_EASE },
} as const

export const fadeIn = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  transition: { duration: MOTION_DURATION, ease: MOTION_EASE },
} as const

export const pressable = {
  whileHover: { scale: 1.02 },
  whileTap: { scale: 0.98 },
  transition: { type: "spring" as const, stiffness: 400, damping: 17 },
} as const

export const staggerContainer = {
  initial: {},
  animate: {
    transition: {
      staggerChildren: STAGGER_DELAY,
    },
  },
} as const

export const staggerItem = {
  initial: { opacity: 0, y: 8 },
  animate: {
    opacity: 1,
    y: 0,
    transition: { duration: MOTION_DURATION, ease: MOTION_EASE },
  },
} as const
