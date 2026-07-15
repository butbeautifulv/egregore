"use client"

import type { Table } from "@tanstack/react-table"
import { Columns3Icon } from "lucide-react"
import { Button } from "@/vendor/gui/ui/button"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/vendor/gui/ui/dropdown-menu"
import { MIN_VISIBLE_DATA_TABLE_COLUMNS } from "@/vendor/gui/lib/data-table/column-visibility"

export function DataTableColumnToggle<TData>({ table }: { table: Table<TData> }) {
  const visibleCount = table.getVisibleLeafColumns().length

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm">
          <Columns3Icon data-icon="inline-start" />
          Колонки
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        {table
          .getAllColumns()
          .filter((column) => column.getCanHide())
          .map((column) => {
            const isVisible = column.getIsVisible()
            const hideLocked = isVisible && visibleCount <= MIN_VISIBLE_DATA_TABLE_COLUMNS

            return (
              <DropdownMenuCheckboxItem
                key={column.id}
                className="capitalize"
                checked={isVisible}
                disabled={hideLocked}
                onCheckedChange={(value) => {
                  if (!value && hideLocked) return
                  column.toggleVisibility(!!value)
                }}
              >
                {typeof column.columnDef.header === "string"
                  ? column.columnDef.header
                  : (column.columnDef.meta?.title ?? column.id)}
              </DropdownMenuCheckboxItem>
            )
          })}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
