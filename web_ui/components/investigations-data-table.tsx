"use client"

import { useMemo } from "react"
import type { ColumnFiltersState } from "@tanstack/react-table"

import type { InvestigationSummary } from "@/lib/types"
import {
  createInvestigationColumns,
  investigationGlobalFilter,
} from "@/lib/data-table/columns/investigation-columns"
import { EmptyTableState } from "@/vendor/gui/layout/empty-table-state"
import { DataTable } from "@/vendor/gui/data-table/data-table"
import { DataTableFacetedFilter } from "@/vendor/gui/data-table/data-table-faceted-filter"

export function InvestigationsDataTable({
  investigations,
  columnFilters,
  onColumnFiltersChange,
}: {
  investigations: InvestigationSummary[]
  columnFilters?: ColumnFiltersState
  onColumnFiltersChange?: (filters: ColumnFiltersState) => void
}) {
  const columns = useMemo(() => createInvestigationColumns(), [])

  if (investigations.length === 0) {
    return (
      <EmptyTableState
        title="No work orders yet"
        description="Start a new work order above to populate this list."
      />
    )
  }

  return (
    <DataTable
      columns={columns}
      data={investigations}
      searchPlaceholder="Search by id, goal, or status…"
      globalFilterFn={investigationGlobalFilter}
      columnFilters={columnFilters}
      onColumnFiltersChange={onColumnFiltersChange}
      initialSorting={[{ id: "updated_at", desc: true }]}
      pageSize={20}
      renderFilters={(table) => {
        const statusColumn = table.getColumn("status")
        if (!statusColumn) return null
        return <DataTableFacetedFilter column={statusColumn} title="Status" />
      }}
      empty={
        <EmptyTableState
          title="No matching work orders"
          description="Try adjusting search or status filters."
        />
      }
    />
  )
}
