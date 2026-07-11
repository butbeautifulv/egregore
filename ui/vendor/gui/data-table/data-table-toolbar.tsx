"use client"

import type { Table } from "@tanstack/react-table"
import { Input } from "@/vendor/gui/ui/input"
import { DataTableColumnToggle } from "@/vendor/gui/data-table/data-table-column-toggle"

export function DataTableToolbar<TData>({
  table,
  searchPlaceholder = "Поиск…",
  filters,
  showColumnToggle = true,
}: {
  table: Table<TData>
  searchPlaceholder?: string
  filters?: React.ReactNode
  showColumnToggle?: boolean
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Input
        placeholder={searchPlaceholder}
        value={(table.getState().globalFilter as string) ?? ""}
        onChange={(e) => table.setGlobalFilter(e.target.value)}
        className="min-w-[16rem] flex-1 max-w-lg"
      />
      {filters}
      {showColumnToggle && <DataTableColumnToggle table={table} />}
    </div>
  )
}
