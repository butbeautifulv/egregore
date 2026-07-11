import Link from "next/link"
import type { ColumnDef, FilterFn, Row } from "@tanstack/react-table"

import type { InvestigationSummary } from "@/lib/types"
import { DataTableColumnHeader } from "@/vendor/gui/data-table/data-table-column-header"
import { FACETED_COLUMN_META } from "@/vendor/gui/lib/data-table/faceted-column"
import { facetedFilter } from "@/vendor/gui/lib/data-table/faceted-column"
import { formatDisplayDate } from "@/vendor/gui/lib/datetime/format"
import { getFilterTimeZone } from "@/vendor/gui/lib/datetime/filter-timezone"
import { Badge } from "@/vendor/gui/ui/badge"
import { OverflowText } from "@/vendor/gui/layout/overflow-text"

function formatInvestigationUpdated(value?: string) {
  if (!value) return "—"
  return formatDisplayDate(value, getFilterTimeZone())
}

function investigationUpdatedTimestamp(value?: string) {
  if (!value) return 0
  const ts = Date.parse(value)
  return Number.isNaN(ts) ? 0 : ts
}

function compareInvestigationUpdated(
  left: Row<InvestigationSummary>,
  right: Row<InvestigationSummary>,
) {
  return (
    investigationUpdatedTimestamp(left.original.updated_at) -
    investigationUpdatedTimestamp(right.original.updated_at)
  )
}

const investigationPersonaFilter: FilterFn<InvestigationSummary> = (
  row,
  _columnId,
  filterValue,
) => {
  const values = filterValue as string[] | undefined
  if (!values?.length) return true
  return values.some((persona) => (row.original.completed_personas ?? []).includes(persona))
}

export function createInvestigationColumns(): ColumnDef<InvestigationSummary>[] {
  return [
    {
      accessorKey: "investigation_id",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Work order" />,
      cell: ({ row }) => (
        <Link
          href={`/work-orders/${row.original.investigation_id}`}
          className="text-primary font-medium hover:underline"
        >
          <OverflowText>{row.original.investigation_id}</OverflowText>
        </Link>
      ),
      meta: { cellClassName: "w-[18%]" },
    },
    {
      accessorKey: "status",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Status" />,
      cell: ({ row }) => <Badge variant="outline">{row.original.status}</Badge>,
      filterFn: facetedFilter,
      meta: { ...FACETED_COLUMN_META, title: "Status", cellClassName: "w-[10%]" },
    },
    {
      accessorKey: "updated_at",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Updated" />,
      cell: ({ row }) => (
        <span className="text-muted-foreground text-xs tabular-nums">
          {formatInvestigationUpdated(row.original.updated_at)}
        </span>
      ),
      filterFn: facetedFilter,
      sortingFn: compareInvestigationUpdated,
      meta: {
        ...FACETED_COLUMN_META,
        title: "Updated",
        valueType: "date",
        cellClassName: "w-[14%]",
      },
    },
    {
      id: "personas",
      accessorFn: (row) => (row.completed_personas ?? []).join(", "),
      header: ({ column }) => <DataTableColumnHeader column={column} title="Personas" />,
      cell: ({ row }) => (
        <div className="flex flex-wrap gap-1">
          {(row.original.completed_personas ?? []).length > 0 ? (
            (row.original.completed_personas ?? []).map((persona) => (
              <Badge key={persona} variant="secondary" className="text-[10px]">
                {persona}
              </Badge>
            ))
          ) : (
            <span className="text-muted-foreground text-xs">—</span>
          )}
        </div>
      ),
      filterFn: investigationPersonaFilter,
      meta: { ...FACETED_COLUMN_META, title: "Personas", cellClassName: "w-[16%]" },
    },
    {
      accessorKey: "goal",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Goal" />,
      cell: ({ row }) => <OverflowText className="text-muted-foreground">{row.original.goal || "—"}</OverflowText>,
      meta: { cellClassName: "w-[42%]" },
    },
  ]
}

export function investigationGlobalFilter(row: InvestigationSummary, _columnId: string, filterValue: string) {
  const needle = filterValue.trim().toLowerCase()
  if (!needle) return true
  return (
    row.investigation_id.toLowerCase().includes(needle) ||
    row.goal.toLowerCase().includes(needle) ||
    row.status.toLowerCase().includes(needle)
  )
}
