"use client"

import { useMemo } from "react"
import { Cell, Pie, PieChart } from "recharts"
import type { ColumnFiltersState } from "@tanstack/react-table"

import { InvestigationChartCard } from "@/components/investigation-chart-card"
import {
  DashboardChartLayout,
  DashboardChartLegend,
  PieSliceLabel,
  chartMetrics,
  formatChartLegendLabel,
  INACTIVE_OPACITY,
  type InvestigationChartSize,
} from "@/components/investigation-chart-shared"
import {
  hasInvestigationChartFilter,
  isInvestigationChartFilterActive,
} from "@/lib/dashboard/investigation-chart-filters"
import type { InvestigationSummary } from "@/lib/types"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/vendor/gui/ui/chart"
import { cn } from "@/vendor/gui/utils"

const CHART_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
]

type ChartRow = {
  key: string
  label: string
  count: number
  fill: string
}

function buildStatusRows(investigations: InvestigationSummary[]): ChartRow[] {
  const counts = new Map<string, number>()
  for (const item of investigations) {
    counts.set(item.status, (counts.get(item.status) ?? 0) + 1)
  }
  return [...counts.entries()].map(([status, count], index) => ({
    key: status,
    label: status,
    count,
    fill: CHART_COLORS[index % CHART_COLORS.length] ?? "var(--chart-1)",
  }))
}

function buildPersonaRows(investigations: InvestigationSummary[]): ChartRow[] {
  const counts = new Map<string, number>()
  for (const item of investigations) {
    for (const persona of item.completed_personas ?? []) {
      counts.set(persona, (counts.get(persona) ?? 0) + 1)
    }
  }
  return [...counts.entries()]
    .sort((left, right) => right[1] - left[1])
    .slice(0, 8)
    .map(([persona, count], index) => ({
      key: persona,
      label: persona,
      count,
      fill: CHART_COLORS[index % CHART_COLORS.length] ?? "var(--chart-1)",
    }))
}

function buildChartConfig(rows: ChartRow[]): ChartConfig {
  return rows.reduce<ChartConfig>((acc, row, index) => {
    acc[row.key] = {
      label: row.label,
      color: row.fill ?? `var(--chart-${(index % 5) + 1})`,
    }
    return acc
  }, { count: { label: "Count" } })
}

function InvestigationPieChartSection({
  rows,
  columnId,
  columnFilters,
  onSliceClick,
  size = "card",
}: {
  rows: ChartRow[]
  columnId: "status" | "personas"
  columnFilters: ColumnFiltersState
  onSliceClick?: (key: string) => void
  size?: InvestigationChartSize
}) {
  const chartConfig = buildChartConfig(rows)
  const total = rows.reduce((sum, row) => sum + row.count, 0)
  const filterActive = hasInvestigationChartFilter(columnFilters, columnId)
  const metrics = chartMetrics(size)
  const isCard = size === "card"

  const legendItems = rows.map((row) => ({
    key: row.key,
    label: formatChartLegendLabel(row.label, row.count, total),
    color: row.fill,
    active: isInvestigationChartFilterActive(columnFilters, columnId, row.key),
    disabled: row.count === 0,
  }))

  const chart = (
    <div
      className={cn(
        "relative mx-auto",
        isCard ? "flex h-full w-full items-center justify-center" : "w-full",
      )}
    >
      <div
        className={cn(
          "relative",
          isCard
            ? "aspect-square h-full max-h-full"
            : cn("mx-auto aspect-square w-full", metrics.pieMaxH),
        )}
      >
        <ChartContainer
          config={chartConfig}
          className={cn("aspect-square h-full w-full", !isCard && metrics.pieMaxH)}
          initialDimension={size === "expanded" ? { width: 480, height: 480 } : undefined}
        >
          <PieChart margin={{ top: 12, right: 20, bottom: 12, left: 20 }}>
            <ChartTooltip content={<ChartTooltipContent hideLabel />} />
            <Pie
              data={rows}
              dataKey="count"
              nameKey="label"
              cx="50%"
              cy="50%"
              innerRadius="40%"
              outerRadius={metrics.pieOuterRadius}
              strokeWidth={2}
              className={onSliceClick ? "cursor-pointer" : undefined}
              label={PieSliceLabel}
              labelLine={false}
              onClick={(_, index) => {
                const entry = rows[index]
                if (entry && onSliceClick) onSliceClick(entry.key)
              }}
            >
              {rows.map((row) => {
                const active = isInvestigationChartFilterActive(columnFilters, columnId, row.key)
                const dimmed = filterActive && !active
                return (
                  <Cell
                    key={row.key}
                    fill={row.fill}
                    fillOpacity={dimmed ? INACTIVE_OPACITY : 1}
                    stroke={active ? "var(--foreground)" : undefined}
                    strokeWidth={active ? 2 : 0}
                  />
                )
              })}
            </Pie>
          </PieChart>
        </ChartContainer>
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <span className={cn("font-bold tabular-nums", metrics.pieCenterClass)}>{total}</span>
        </div>
      </div>
    </div>
  )

  return (
    <DashboardChartLayout
      size={size}
      chart={chart}
      legend={
        <DashboardChartLegend
          items={legendItems}
          onItemClick={onSliceClick}
        />
      }
    />
  )
}

export function InvestigationsStatusCharts({
  investigations,
  columnFilters = [],
  onStatusClick,
  onPersonaClick,
}: {
  investigations: InvestigationSummary[]
  columnFilters?: ColumnFiltersState
  onStatusClick?: (status: string) => void
  onPersonaClick?: (persona: string) => void
}) {
  const statusRows = useMemo(() => buildStatusRows(investigations), [investigations])
  const personaRows = useMemo(() => buildPersonaRows(investigations), [investigations])

  if (investigations.length === 0) return null

  return (
    <div className="grid gap-4 @2xl/main:grid-cols-2">
      <InvestigationChartCard
        className="h-full"
        title="Work orders by status"
        expandable={statusRows.length > 0}
        renderExpanded={() => (
          <InvestigationPieChartSection
            rows={statusRows}
            columnId="status"
            columnFilters={columnFilters}
            onSliceClick={onStatusClick}
            size="expanded"
          />
        )}
      >
        <InvestigationPieChartSection
          rows={statusRows}
          columnId="status"
          columnFilters={columnFilters}
          onSliceClick={onStatusClick}
        />
      </InvestigationChartCard>

      {personaRows.length > 0 ? (
        <InvestigationChartCard
          className="h-full"
          title="Completed personas"
          expandable
          renderExpanded={() => (
            <InvestigationPieChartSection
              rows={personaRows}
              columnId="personas"
              columnFilters={columnFilters}
              onSliceClick={onPersonaClick}
              size="expanded"
            />
          )}
        >
          <InvestigationPieChartSection
            rows={personaRows}
            columnId="personas"
            columnFilters={columnFilters}
            onSliceClick={onPersonaClick}
          />
        </InvestigationChartCard>
      ) : null}
    </div>
  )
}
