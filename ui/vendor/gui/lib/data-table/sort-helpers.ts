import type { Row } from "@tanstack/react-table"

export const dateSortFn = <TData,>(a: Row<TData>, b: Row<TData>, columnId: string) => {
  const aVal = a.getValue(columnId)
  const bVal = b.getValue(columnId)
  const aTime = aVal ? new Date(aVal as string).getTime() : 0
  const bTime = bVal ? new Date(bVal as string).getTime() : 0
  return aTime - bTime
}

export const numberSortFn = <TData,>(a: Row<TData>, b: Row<TData>, columnId: string) => {
  const aVal = Number(a.getValue(columnId) ?? 0)
  const bVal = Number(b.getValue(columnId) ?? 0)
  return aVal - bVal
}
