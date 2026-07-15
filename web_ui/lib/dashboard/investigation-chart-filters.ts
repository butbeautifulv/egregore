import type { ColumnFiltersState } from "@tanstack/react-table"

function filterValues(filters: ColumnFiltersState, id: string): string[] {
  return (filters.find((filter) => filter.id === id)?.value as string[]) ?? []
}

function setFilter(
  filters: ColumnFiltersState,
  id: string,
  values: string[] | undefined,
): ColumnFiltersState {
  const rest = filters.filter((filter) => filter.id !== id)
  if (!values?.length) return rest
  return [...rest, { id, value: values }]
}

export function hasInvestigationChartFilter(
  filters: ColumnFiltersState,
  columnId: "status" | "personas",
): boolean {
  return filters.some((filter) => filter.id === columnId)
}

export function isInvestigationChartFilterActive(
  filters: ColumnFiltersState,
  columnId: "status" | "personas",
  value: string,
): boolean {
  const values = filterValues(filters, columnId)
  return values.length === 1 && values[0] === value
}

export function toggleInvestigationChartFilter(
  filters: ColumnFiltersState,
  columnId: "status" | "personas",
  value: string,
): ColumnFiltersState {
  const current = filterValues(filters, columnId)
  if (current.length === 1 && current[0] === value) {
    return setFilter(filters, columnId, undefined)
  }
  return setFilter(filters, columnId, [value])
}
