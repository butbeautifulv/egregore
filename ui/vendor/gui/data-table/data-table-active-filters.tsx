"use client"

import type { Table } from "@tanstack/react-table"
import { XIcon } from "lucide-react"
import { OverflowText } from "@/vendor/gui/layout/overflow-text"
import { Badge } from "@/vendor/gui/ui/badge"
import { Button } from "@/vendor/gui/ui/button"
import { formatFilterDisplayValue } from "@/vendor/gui/lib/data-table/format-filter-value"

export function DataTableActiveFilters<TData>({ table }: { table: Table<TData> }) {
  const timeZone =
    Intl.DateTimeFormat().resolvedOptions().timeZone ?? "Europe/Moscow"
  const columnFilters = table.getState().columnFilters
  if (columnFilters.length === 0) return null

  return (
    <div className="flex min-w-0 max-w-full flex-wrap items-center gap-2">
      {columnFilters.map((filter) => {
        const column = table.getColumn(filter.id)
        const meta = column?.columnDef.meta
        const title = meta?.title ?? filter.id
        const values = (filter.value as string[]) ?? []

        return values.map((value) => {
          const display = formatFilterDisplayValue(value, meta, timeZone)
          const label = `${title}: ${display}`

          return (
            <Badge
              key={`${filter.id}-${value}`}
              variant="secondary"
              className="!w-auto max-w-[min(100%,20rem)] min-w-0 shrink gap-1 overflow-hidden pr-1"
            >
              <span className="min-w-0 flex-1 basis-0 overflow-hidden">
                <OverflowText className="w-full">{label}</OverflowText>
              </span>
              <button
                type="button"
                className="shrink-0 rounded-sm hover:bg-muted"
                onClick={() => {
                  const next = values.filter((v) => v !== value)
                  column?.setFilterValue(next.length ? next : undefined)
                }}
              >
                <XIcon className="size-3" />
                <span className="sr-only">Убрать фильтр</span>
              </button>
            </Badge>
          )
        })
      })}
      <Button
        variant="ghost"
        size="sm"
        className="h-7 shrink-0 px-2"
        onClick={() => table.resetColumnFilters()}
      >
        Сбросить все
      </Button>
    </div>
  )
}
