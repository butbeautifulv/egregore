"use client"

import { useEffect, useId, useRef, useState } from "react"

import { useTheme } from "@/vendor/gui/theme/theme-provider"
import { cn } from "@/vendor/gui/utils"

export function MermaidDiagram({
  chart,
  className,
}: {
  chart: string
  className?: string
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)
  const renderId = useId().replace(/:/g, "")
  const { resolvedTheme } = useTheme()

  useEffect(() => {
    let cancelled = false
    const container = containerRef.current
    if (!container || !chart.trim()) {
      return undefined
    }

    ;(async () => {
      try {
        const mermaid = (await import("mermaid")).default
        mermaid.initialize({
          startOnLoad: false,
          theme: resolvedTheme === "dark" ? "dark" : "neutral",
          securityLevel: "strict",
          flowchart: {
            htmlLabels: true,
            curve: "basis",
          },
        })
        const renderKey = `mermaid-${renderId}-${Date.now()}`
        const { svg, bindFunctions } = await mermaid.render(renderKey, chart)
        if (cancelled) return
        container.innerHTML = svg
        bindFunctions?.(container)
        setError(null)
      } catch (exc) {
        if (!cancelled) {
          setError(exc instanceof Error ? exc.message : String(exc))
        }
      }
    })()

    return () => {
      cancelled = true
      container.innerHTML = ""
    }
  }, [chart, renderId, resolvedTheme])

  if (!chart.trim()) {
    return null
  }

  if (error) {
    return (
      <pre className="text-muted-foreground overflow-auto border p-2 text-xs whitespace-pre-wrap">
        {error}
      </pre>
    )
  }

  return (
    <div
      ref={containerRef}
      className={cn(
        "bg-background overflow-x-auto border p-3 [&_svg]:mx-auto [&_svg]:max-w-full",
        className,
      )}
    />
  )
}
