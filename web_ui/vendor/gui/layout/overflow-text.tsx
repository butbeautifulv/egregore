"use client"

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react"
import { motion, useReducedMotion } from "motion/react"
import { cn } from "@/vendor/gui/utils"

const MARQUEE_GAP = "\u00a0\u00a0"

export function OverflowText({
  children,
  className,
  variant = "block",
  title,
}: {
  children: string
  className?: string
  variant?: "block" | "inline"
  /** Tooltip when text is truncated (marquee disabled via prefers-reduced-motion). */
  title?: string
}) {
  const containerRef = useRef<HTMLSpanElement>(null)
  const measureRef = useRef<HTMLSpanElement>(null)
  const staticRef = useRef<HTMLSpanElement>(null)
  const [canOverflow, setCanOverflow] = useState(false)
  const [hovering, setHovering] = useState(false)
  const [marqueeDuration, setMarqueeDuration] = useState(6)
  const shouldReduceMotion = useReducedMotion()

  const measure = useCallback(() => {
    const container = containerRef.current
    const probe = measureRef.current
    const staticEl = staticRef.current
    if (!container || !probe) return

    const available = container.getBoundingClientRect().width
    const textWidth = probe.getBoundingClientRect().width
    const scrollOverflow =
      staticEl != null && staticEl.scrollWidth > staticEl.clientWidth + 1
    const overflows = available > 0 && (textWidth > available + 1 || scrollOverflow)

    setCanOverflow(overflows)
    if (overflows) {
      setMarqueeDuration(Math.max(4, Math.min(16, textWidth / 28)))
    }
  }, [])

  useLayoutEffect(() => {
    measure()
  }, [measure, children])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const observer = new ResizeObserver(() => measure())
    observer.observe(container)

    if (document.fonts?.ready) {
      document.fonts.ready.then(measure)
    }

    return () => observer.disconnect()
  }, [measure])

  const showMarquee = hovering && canOverflow && !shouldReduceMotion
  const fullTitle = title ?? children
  const segment = `${children}${MARQUEE_GAP}`

  const startMarquee = () => {
    if (canOverflow) setHovering(true)
  }

  const stopMarquee = () => {
    setHovering(false)
  }

  return (
    <span
      ref={containerRef}
      className={cn(
        "relative min-w-0 overflow-hidden",
        variant === "block" ? "block" : "inline-block max-w-full",
        className
      )}
      title={canOverflow ? fullTitle : undefined}
      onMouseEnter={startMarquee}
      onMouseLeave={stopMarquee}
      onFocus={startMarquee}
      onBlur={stopMarquee}
    >
      <span
        ref={measureRef}
        aria-hidden
        className="pointer-events-none absolute top-0 left-0 -z-10 opacity-0 whitespace-nowrap"
      >
        {children}
      </span>

      <span
        ref={staticRef}
        className={cn(
          "min-w-0 truncate whitespace-nowrap",
          variant === "block" ? "block w-full" : "inline-block max-w-full",
          showMarquee && "opacity-0"
        )}
      >
        {children}
      </span>

      {showMarquee ? (
        <motion.span
          key={children}
          className="absolute inset-y-0 left-0 flex items-center whitespace-nowrap"
          initial={{ x: 0 }}
          animate={{ x: "-50%" }}
          transition={{
            duration: marqueeDuration,
            ease: "linear",
            repeat: Infinity,
          }}
          aria-hidden
        >
          <span className="shrink-0">{segment}</span>
          <span className="shrink-0">{segment}</span>
        </motion.span>
      ) : null}
    </span>
  )
}
