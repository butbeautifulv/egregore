import type { FilterFn, RowData } from "@tanstack/react-table"
import { normalizeFilterValue } from "@/vendor/gui/lib/data-table/format-filter-value"

export const FACETED_COLUMN_META = { faceted: true } as const

export const facetedFilterFn: FilterFn<unknown> = (row, columnId, filterValue) => {
  const values = filterValue as string[] | undefined
  if (!values?.length) return true
  const cell = row.getAllCells().find((c) => c.column.id === columnId)
  const meta = cell?.column.columnDef.meta
  return values.includes(normalizeFilterValue(row.getValue(columnId), meta))
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const facetedFilter = facetedFilterFn as FilterFn<any>

declare module "@tanstack/react-table" {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  interface ColumnMeta<TData extends RowData, TValue> {
    faceted?: boolean
    title?: string
    cellClassName?: string
    valueType?: "date" | "datetime"
    valueLabels?: Record<string, string>
    role?: "actions"
  }
}
