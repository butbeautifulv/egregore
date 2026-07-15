import type { ColumnDef, VisibilityState } from "@tanstack/react-table"

export const MIN_VISIBLE_DATA_TABLE_COLUMNS = 2

export function getColumnDefId<T>(column: ColumnDef<T, unknown>, index: number): string {
  if (column.id) return column.id
  const accessorKey = "accessorKey" in column ? column.accessorKey : undefined
  if (typeof accessorKey === "string") return accessorKey
  return String(index)
}

export function getColumnDefIds<T>(columns: ColumnDef<T, unknown>[]): string[] {
  return columns.map(getColumnDefId)
}

export function countVisibleColumns(
  columnIds: string[],
  visibility: VisibilityState
): number {
  return columnIds.filter((id) => visibility[id] !== false).length
}

export function minVisibleColumnCount(columnIds: string[]): number {
  return Math.min(MIN_VISIBLE_DATA_TABLE_COLUMNS, columnIds.length)
}

export function clampColumnVisibility(
  columnIds: string[],
  prev: VisibilityState,
  next: VisibilityState
): VisibilityState {
  if (countVisibleColumns(columnIds, next) >= minVisibleColumnCount(columnIds)) {
    return next
  }
  return prev
}
