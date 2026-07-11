"use client"

import { useCallback, useState } from "react"
import type { ColumnFiltersState } from "@tanstack/react-table"

import { listInvestigations, type InvestigationSummary } from "@/lib/api-client"
import { ApiErrorAlert } from "@/components/api-error-alert"
import { ChatPanel } from "@/components/chat-panel"
import { InfraStatusBanner } from "@/components/infra-status-banner"
import { InvestigationsDataTable } from "@/components/investigations-data-table"
import { InvestigationsStatusCharts } from "@/components/investigations-status-charts"
import { toggleInvestigationChartFilter } from "@/lib/dashboard/investigation-chart-filters"
import { useApiQuery } from "@/hooks/use-api-query"
import {
  ChartCardsGridSkeleton,
  TableRowsSkeleton,
  TableToolbarSkeleton,
} from "@/components/skeletons"

export function InvestigationsAsyncPanel() {
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])
  const fetcher = useCallback(async () => {
    const response = await listInvestigations()
    return response.investigations
  }, [])
  const { data, error, loading, refresh, isStale } = useApiQuery<InvestigationSummary[]>(
    fetcher,
    [],
    { fallback: "Failed to load work orders" },
  )

  const investigations = data ?? []
  const listLoading = loading && !data

  const handleStatusClick = useCallback((status: string) => {
    setColumnFilters((previous) => toggleInvestigationChartFilter(previous, "status", status))
  }, [])

  const handlePersonaClick = useCallback((persona: string) => {
    setColumnFilters((previous) => toggleInvestigationChartFilter(previous, "personas", persona))
  }, [])

  return (
    <div className="flex flex-col gap-6">
      <InfraStatusBanner />

      <ChatPanel className="w-full" />

      {listLoading ? (
        <>
          <ChartCardsGridSkeleton />
          <TableToolbarSkeleton />
          <TableRowsSkeleton rows={8} />
        </>
      ) : (
        <>
          {!error ? (
            <InvestigationsStatusCharts
              investigations={investigations}
              columnFilters={columnFilters}
              onStatusClick={handleStatusClick}
              onPersonaClick={handlePersonaClick}
            />
          ) : null}

          {error ? (
            <>
              <p className="text-muted-foreground text-sm">
                Work order list is unavailable. You can still try starting a new work order with the
                start card above.
              </p>
              <ApiErrorAlert
                error={error}
                fallback="Failed to load work orders"
                onRetry={() => void refresh()}
                isStale={isStale}
              />
            </>
          ) : null}

          <InvestigationsDataTable
            investigations={investigations}
            columnFilters={columnFilters}
            onColumnFiltersChange={setColumnFilters}
          />
        </>
      )}
    </div>
  )
}
