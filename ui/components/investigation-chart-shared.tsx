"use client"

import { OverflowText } from "@/vendor/gui/layout/overflow-text"
import { cn } from "@/vendor/gui/utils"

export const INACTIVE_OPACITY = 0.35
export const MIN_PIE_INSIDE_PERCENT = 0.08

export const CARD_CHART_HEIGHT = "h-72"
export const CARD_LEGEND_HEIGHT = "h-14"

export type InvestigationChartSize = "card" | "expanded"

export function formatChartLegendLabel(label: string, count: number, total: number) {
  const pct = total > 0 ? Math.round((count / total) * 100) : 0
  return `${label} (${count}) ${pct}%`
}

export function DashboardChartLayout({
  size,
  chart,
  legend,
}: {
  size: InvestigationChartSize
  chart: React.ReactNode
  legend: React.ReactNode
}) {
  if (size === "expanded") {
    return (
      <div className="w-full min-w-0">
        {chart}
        {legend}
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className={cn("shrink-0 overflow-hidden", CARD_CHART_HEIGHT)}>{chart}</div>
      <div className={cn("shrink-0", CARD_LEGEND_HEIGHT)}>{legend}</div>
    </div>
  )
}

export function chartMetrics(size: InvestigationChartSize) {
  if (size === "expanded") {
    return {
      pieMaxH: "max-h-80",
      pieOuterRadius: "72%",
      pieCenterClass: "text-4xl",
    }
  }

  return {
    pieMaxH: "max-h-52",
    pieOuterRadius: "68%",
    pieCenterClass: "text-2xl",
  }
}

type PieLabelProps = {
  cx?: number
  cy?: number
  midAngle?: number
  innerRadius?: number
  outerRadius?: number
  percent?: number
  value?: number
}

export function PieSliceLabel({
  cx = 0,
  cy = 0,
  midAngle = 0,
  innerRadius = 0,
  outerRadius = 0,
  percent = 0,
  value = 0,
}: PieLabelProps) {
  if (!value || percent < 0.02) return null

  const RADIAN = Math.PI / 180
  const angle = -midAngle * RADIAN

  if (percent >= MIN_PIE_INSIDE_PERCENT) {
    const radius = innerRadius + (outerRadius - innerRadius) * 0.5
    const x = cx + radius * Math.cos(angle)
    const y = cy + radius * Math.sin(angle)
    return (
      <text
        x={x}
        y={y}
        textAnchor="middle"
        dominantBaseline="central"
        className="fill-background text-[10px] font-semibold"
      >
        {value}
      </text>
    )
  }

  const radius = outerRadius + 14
  const x = cx + radius * Math.cos(angle)
  const y = cy + radius * Math.sin(angle)
  const anchor = x > cx ? "start" : "end"
  const lineEnd = outerRadius + 4
  const lineX = cx + lineEnd * Math.cos(angle)
  const lineY = cy + lineEnd * Math.sin(angle)

  return (
    <g>
      <line
        x1={lineX}
        y1={lineY}
        x2={x}
        y2={y}
        className="stroke-muted-foreground"
        strokeWidth={1}
      />
      <text
        x={x}
        y={y}
        textAnchor={anchor}
        dominantBaseline="central"
        className="fill-foreground text-[10px] font-semibold"
      >
        {value}
      </text>
    </g>
  )
}

export function DashboardChartLegend({
  items,
  onItemClick,
}: {
  items: {
    key: string
    label: string
    color: string
    active?: boolean
    visible?: boolean
    disabled?: boolean
  }[]
  onItemClick?: (key: string) => void
}) {
  return (
    <div className="flex h-full flex-col overflow-hidden border-t pt-2">
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="grid grid-cols-2 gap-x-2 gap-y-1 sm:grid-cols-3">
          {items.map((item) => {
            const isVisible = item.visible ?? true
            const content = (
              <>
                <span
                  className={cn(
                    "mt-0.5 h-2 w-2 shrink-0 rounded-[2px]",
                    !isVisible && "opacity-40",
                  )}
                  style={{ backgroundColor: item.color }}
                />
                <OverflowText
                  className={cn("min-w-0 flex-1", !isVisible && "line-through")}
                >
                  {item.label}
                </OverflowText>
              </>
            )

            if (!onItemClick) {
              return (
                <div
                  key={item.key}
                  className={cn(
                    "inline-flex min-w-0 items-start gap-1.5 text-left text-[11px] leading-tight",
                    item.active ? "font-medium text-foreground" : "text-muted-foreground",
                    !isVisible && "opacity-50",
                  )}
                >
                  {content}
                </div>
              )
            }

            return (
              <button
                key={item.key}
                type="button"
                disabled={item.disabled}
                className={cn(
                  "inline-flex min-w-0 items-start gap-1.5 text-left text-[11px] leading-tight",
                  !item.disabled && "cursor-pointer hover:opacity-80",
                  item.disabled && "cursor-not-allowed opacity-60",
                  item.active ? "font-medium text-foreground" : "text-muted-foreground",
                  !isVisible && "opacity-50",
                )}
                onClick={() => {
                  if (!item.disabled) onItemClick(item.key)
                }}
              >
                {content}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
